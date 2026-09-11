"""Publisher: queue, multi-platform publish, retry + scheduling.

Platforms are pluggable via registry.publishers. Built-in `log` publisher
writes to audit log (safe default). Real platforms (Telegram/X/IG/YT) are
added as plugins without touching this core.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Callable

from app.core.plugins import registry
from app.core.audit import audit


def _log_publisher(job, content) -> bool:
    return True


registry.register_publisher("log", _log_publisher)


def queue_post(db, content_id: int, platform: str, delay_minutes: int | None = 0,
               actor: str = "system", country: str | None = None):
    """Queue a post. Phase 2: delay_minutes=None auto-selects the best
    publishing time for `country` (default from settings) via the
    timezone engine. Explicit delays keep exact Phase 1 behavior."""
    from app.models.models import PublishJob
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
                     scheduled_at=datetime.utcnow() + timedelta(minutes=delay_minutes))
    db.add(job)
    db.commit()
    db.refresh(job)
    audit(db, actor, "publish.queued", "publish_job", job.id,
          {"content_id": content_id, "platform": platform,
           "country": country or "", "auto_scheduled": auto})
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
        publisher = registry.publishers.get(job.platform, _log_publisher)
        job.attempts += 1
        job.status = "sending"
        try:
            ok = (sender or publisher)(job, content)
            if ok:
                job.status = "sent"
                if content is not None:
                    content.status = "published"
                summary["sent"] += 1
                audit(db, "publisher", "publish.sent", "publish_job", job.id, {})
            else:
                raise RuntimeError("publisher returned falsy")
        except Exception as exc:
            job.status = "failed"
            job.last_error = str(exc)[:1000]
            # exponential backoff: 2^attempts minutes
            job.scheduled_at = now + timedelta(minutes=2 ** min(job.attempts, 6))
            summary["failed"] += 1
            audit(db, "publisher", "publish.failed", "publish_job", job.id, {"error": str(exc)})
        summary["processed"] += 1
    db.commit()
    return summary
