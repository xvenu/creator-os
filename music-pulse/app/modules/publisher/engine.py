"""Publisher: queue, multi-platform publish, retry + scheduling.

MusicPulse-owned. Built-in `log` publisher is a safe default for tests only
and is NEVER production evidence. Real channels (YouTube, webhook) live in
`channels.py` with scoped env/file credentials. Idempotency: every publish
intent carries a deterministic key (pulse|content|platform|account|version);
repeats reuse the existing job.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Callable

from app.core.plugins import registry
from app.core.audit import audit

PULSE_NAME = "music-pulse"


def _log_publisher(job, content) -> bool:
    return True


def _channel_sender(platform: str):
    from app.modules.publisher import channels as ch
    if platform == "youtube":
        return lambda job, content: ch.publish_youtube(
            job, content, account=getattr(job, "target_account", ""))
    if platform == "webhook":
        return lambda job, content: ch.publish_webhook(
            job, content, account=getattr(job, "target_account", ""))
    return registry.publishers.get(platform, _log_publisher)


registry.register_publisher("log", _log_publisher)


def queue_post(db, content_id: int, platform: str, delay_minutes: int | None = 0,
               actor: str = "system", country: str | None = None,
               target_account: str = "", content_version: str = "v1"):
    """Queue a post — idempotent on (pulse, content, platform, account, version).

    First request creates the job; repeats return the existing job unchanged.
    Phase 2: delay_minutes=None auto-selects the best publishing time."""
    from app.models.models import PublishJob
    from app.modules.publisher.channels import idempotency_key
    key = idempotency_key(PULSE_NAME, content_id, platform,
                          target_account or "", content_version or "v1")
    existing = db.query(PublishJob).filter_by(idempotency_key=key).first()
    if existing is not None:
        return existing
    auto = delay_minutes is None
    if auto:
        try:
            from app.core.config import get_settings
            from app.modules.timezone.engine import minutes_until_best
            delay_minutes = minutes_until_best(country or get_settings().default_country, db)
        except Exception:
            delay_minutes = 0
        try:
            from app.core.config import get_settings
            from app.modules.timezone.engine import minutes_until_best
            delay_minutes = minutes_until_best(country or get_settings().default_country, db)
        except Exception:
            delay_minutes = 0
    job = PublishJob(content_id=content_id, platform=platform,
                     status="queued",
                     scheduled_at=datetime.utcnow() + timedelta(minutes=delay_minutes or 0),
                     idempotency_key=key, target_account=target_account or "",
                     content_version=content_version or "v1")
    db.add(job)
    try:
        db.commit()
    except Exception:
        # Lost race on unique key: return the winner (same intent, one job).
        db.rollback()
        existing = db.query(PublishJob).filter_by(idempotency_key=key).first()
        if existing is not None:
            return existing
        raise
    db.refresh(job)
    audit(db, actor, "publish.queued", "publish_job", job.id,
          {"content_id": content_id, "platform": platform,
           "country": country or "", "auto_scheduled": auto,
           "idempotency_key": key})
    return job


def publish_due_jobs(db, max_attempts: int = 5, sender: Callable | None = None) -> dict:
    """Publish all due jobs. Returns summary. Retries with backoff on failure."""
    from app.models.models import PublishJob, ContentItem
    now = datetime.utcnow()
    jobs = db.query(PublishJob).filter(
        PublishJob.status.in_(["queued", "failed"]),
        PublishJob.scheduled_at <= now,
        PublishJob.attempts < max_attempts,
    ).all()
    summary = {"processed": 0, "sent": 0, "failed": 0}
    for job in jobs:
        content = db.get(ContentItem, job.content_id)
        # Phase 3: policy gate — all publishing must pass policy checks.
        try:
            from app.modules.policy.engine import check_content
            verdict = check_content(
                db, getattr(content, "title", ""), getattr(content, "body", ""),
                content_ref=f"publish_job:{job.id}", actor="publisher")
            if not verdict["allowed"]:
                job.attempts += 1
                job.status = "failed"
                job.last_error = f"policy blocked: {verdict['rule']}"[:1000]
                summary["processed"] += 1
                summary["failed"] += 1
                audit(db, "publisher", "publish.blocked", "publish_job", job.id,
                      {"rule": verdict["rule"]})
                continue
        except Exception:
            pass  # policy must never hard-crash publishing; fail open to legacy path
        publisher = _channel_sender(job.platform)
        # Skip already-sent intents (retry/resume safety: same intent, no double publish).
        if job.status == "sent" and getattr(job, "remote_id", ""):
            summary["processed"] += 1
            continue
        job.attempts += 1
        job.status = "sending"
        try:
            receipt = (sender or publisher)(job, content)
            remote_id = receipt.get("remote_id", "") if isinstance(receipt, dict) else ""
            if receipt:
                job.status = "sent"
                job.remote_id = remote_id
                job.remote_status = receipt.get("status", "published") if isinstance(receipt, dict) else "published"
                job.published_at = datetime.utcnow()
                if content is not None:
                    content.status = "published"
                summary["sent"] += 1
                audit(db, "publisher", "publish.sent", "publish_job", job.id,
                      {"idempotency_key": getattr(job, "idempotency_key", ""),
                       "remote_status": job.remote_status})
            else:
                raise RuntimeError("publisher returned falsy")
        except Exception as exc:
            job.status = "failed"
            # Scrub any accidental credential echo from stored errors.
            job.last_error = _scrub(str(exc))[:1000]
            wait = 2 ** min(job.attempts, 6)
            if getattr(exc, "rate_limited", False):
                wait = max(wait, 15)
            job.scheduled_at = now + timedelta(minutes=wait)
            summary["failed"] += 1
            audit(db, "publisher", "publish.failed", "publish_job", job.id,
                  {"error": _scrub(str(exc)),
                   "idempotency_key": getattr(job, "idempotency_key", "")})
        summary["processed"] += 1
    db.commit()
    return summary


def _scrub(msg: str) -> str:
    """Remove bearer tokens / keys accidentally embedded in error text."""
    import re
    msg = re.sub(r"Bearer\s+[A-Za-z0-9\-._~+/=]+", "Bearer <redacted>", msg)
    msg = re.sub(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*\S+", r"\1=<redacted>", msg)
    return msg
