"""FootballPulse-owned publishing: queue + deliver with idempotency.

Channels: YouTube (OAuth access token) + generic webhook (real HTTP receipt).
Credentials from env/`_FILE` at call time; missing creds → explicit terminal
error (deployment blocker), never fake success. Rate limits (429) reschedule
with extended backoff. Sync SQLAlchemy session style (matches zoza tracker).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

PULSE_NAME = "football-pulse"


def idempotency_key(package_ref: str, platform: str,
                    account: str = "", version: str = "v1") -> str:
    raw = f"{PULSE_NAME}|{package_ref}|{platform}|{account}|{version}"
    return "pub_" + hashlib.sha256(raw.encode()).hexdigest()[:40]


def _secret(name: str) -> str:
    fp = os.getenv(name + "_FILE", "")
    if fp:
        try:
            v = Path(fp).read_text(encoding="utf-8").strip()
            if v:
                return v
        except OSError:
            pass
    return os.getenv(name, "")


def queue_delivery(session, package_ref: str, platform: str,
                   account: str = "", version: str = "v1",
                   payload: dict | None = None):
    """Idempotent queue: repeats return the existing delivery row."""
    from app.db.models.phase6 import PublicationDelivery
    key = idempotency_key(package_ref, platform, account or "", version or "v1")
    existing = session.query(PublicationDelivery).filter_by(idempotency_key=key).first()
    if existing is not None:
        return existing, False
    row = PublicationDelivery(
        idempotency_key=key, package_ref=package_ref, platform=platform,
        target_account=account or "", content_version=version or "v1",
        status="queued", scheduled_at=dt.datetime.now(dt.timezone.utc))
    session.add(row)
    try:
        session.commit()
    except Exception:
        session.rollback()
        existing = session.query(PublicationDelivery).filter_by(idempotency_key=key).first()
        if existing is not None:
            return existing, False
        raise
    session.refresh(row)
    return row, True


def deliver_due(session, sender=None, max_attempts: int = 5) -> dict:
    """Deliver queued/failed rows due now. Same-intent retries reuse the row."""
    from app.db.models.phase6 import PublicationDelivery
    now = dt.datetime.now(dt.timezone.utc)
    rows = session.query(PublicationDelivery).filter(
        PublicationDelivery.status.in_(["queued", "failed"]),
        PublicationDelivery.scheduled_at <= now,
        PublicationDelivery.attempts < max_attempts).all()
    summary = {"processed": 0, "sent": 0, "failed": 0}
    for row in rows:
        if row.status == "sent" and row.remote_id:
            summary["processed"] += 1
            continue
        row.attempts += 1
        row.status = "sending"
        try:
            fn = sender or _channel(row.platform)
            receipt = fn(row)
            row.status = "sent"
            row.remote_id = str(receipt.get("remote_id", ""))
            row.remote_status = str(receipt.get("status", "published"))
            row.published_at = now
            row.last_error = ""
            summary["sent"] += 1
        except Exception as exc:
            row.status = "failed"
            row.last_error = _scrub(str(exc))[:1000]
            wait_min = 2 ** min(row.attempts, 6)
            if getattr(exc, "rate_limited", False):
                wait_min = max(wait_min, 15)
            row.scheduled_at = now + dt.timedelta(minutes=wait_min)
            summary["failed"] += 1
        summary["processed"] += 1
    session.commit()
    return summary


def _channel(platform: str):
    if platform == "youtube":
        return _youtube
    if platform == "webhook":
        return _webhook
    raise RuntimeError(f"unknown football channel: {platform}")


def _youtube(row) -> dict[str, Any]:
    token = _secret("FOOTBALL_YOUTUBE_ACCESS_TOKEN") or _secret("YOUTUBE_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("youtube credentials missing (FOOTBALL_YOUTUBE_ACCESS_TOKEN); deployment blocker")
    meta = json.dumps({"snippet": {"title": row.package_ref[:100],
                                   "description": f"FootballPulse {row.package_ref}",
                                   "categoryId": "17"},
                       "status": {"privacyStatus": "private"}}).encode()
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=b"", method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            session_url = r.headers.get("Location", "")
    except urllib.error.HTTPError as exc:
        raise _http_err("youtube init", exc)
    if not session_url:
        raise RuntimeError("youtube: no upload session URL (terminal)")
    put = urllib.request.Request(session_url, data=meta, method="PUT",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(put, timeout=60) as r:
            payload = json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        raise _http_err("youtube upload", exc)
    vid = str(payload.get("id", ""))
    if not vid:
        raise RuntimeError("youtube: upload accepted without video id (retryable)")
    return {"remote_id": vid, "status": "published"}


def _webhook(row) -> dict[str, Any]:
    url = os.getenv("FOOTBALL_WEBHOOK_URL", "")
    if not url:
        raise RuntimeError("webhook channel unconfigured (FOOTBALL_WEBHOOK_URL); deployment blocker")
    payload = json.dumps({"idempotency_key": row.idempotency_key, "platform": row.platform,
                          "account": row.target_account, "package_ref": row.package_ref}).encode()
    headers = {"Content-Type": "application/json"}
    token = _secret("FOOTBALL_WEBHOOK_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()[:2000]
            try:
                rid = str(json.loads(body).get("id", body[:64]))
            except Exception:
                rid = body[:64]
    except urllib.error.HTTPError as exc:
        raise _http_err("webhook", exc)
    except OSError as exc:
        err = RuntimeError(f"webhook network failure (retryable): {exc}")
        err.retryable = True  # type: ignore[attr-defined]
        raise err
    return {"remote_id": rid or "webhook-accepted", "status": "published"}


def _http_err(where: str, exc: "urllib.error.HTTPError") -> RuntimeError:
    code = getattr(exc, "code", 0) or 0
    retryable = code == 429 or (500 <= code < 600)
    err = RuntimeError(f"{where} HTTP {code} ({'retryable' if retryable else 'terminal'})")
    err.retryable = retryable  # type: ignore[attr-defined]
    err.rate_limited = (code == 429)  # type: ignore[attr-defined]
    return err


def _scrub(msg: str) -> str:
    import re
    msg = re.sub(r"Bearer\s+[A-Za-z0-9\-._~+/=]+", "Bearer <redacted>", msg)
    msg = re.sub(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*\S+", r"\1=<redacted>", msg)
    return msg
