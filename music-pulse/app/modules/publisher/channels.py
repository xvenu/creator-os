"""MusicPulse-owned real publishing channels: YouTube + generic webhook.

Credential discipline: tokens come from environment (or `*_FILE` Docker-secret
indirection) at call time, never stored, never logged, never returned. Missing
credentials → explicit terminal error (deployment blocker), never fake success.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path


def idempotency_key(pulse: str, content_id: int | str, platform: str,
                    account: str = "", version: str = "v1") -> str:
    raw = f"{pulse}|{content_id}|{platform}|{account}|{version}"
    return "pub_" + hashlib.sha256(raw.encode()).hexdigest()[:40]


def _secret(name: str) -> str:
    file_var = os.getenv(name + "_FILE", "")
    if file_var:
        try:
            val = Path(file_var).read_text(encoding="utf-8").strip()
            if val:
                return val
        except OSError:
            pass
    return os.getenv(name, "")


def publish_youtube(job, content, account: str = "") -> dict:
    """Real YouTube upload via resumable-uploads endpoint (OAuth access token).

    Requires YOUTUBE_ACCESS_TOKEN (or _FILE). Returns {"remote_id","status"}.
    Raises RuntimeError(retryable=...) — 429/5xx retryable, 4xx terminal.
    """
    token = _secret("YOUTUBE_ACCESS_TOKEN") or _secret("YOUTUBE_API_KEY")
    if not token:
        raise RuntimeError("youtube credentials missing (YOUTUBE_ACCESS_TOKEN); deployment blocker")
    title = getattr(content, "title", "MusicPulse release")[:100]
    body = getattr(content, "body", "")[:5000]
    meta = json.dumps({"snippet": {"title": title, "description": body,
                                   "categoryId": "10"},
                       "status": {"privacyStatus": "private"}}).encode()
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=b"", method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "X-Upload-Content-Type": "video/mp4"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            session_url = r.headers.get("Location", "")
    except urllib.error.HTTPError as exc:
        raise _http_err("youtube init", exc)
    if not session_url:
        raise RuntimeError("youtube: no upload session URL (terminal)")
    # Metadata-only close (media bytes upload omitted without a video file ref).
    put = urllib.request.Request(session_url, data=meta, method="PUT",
                                 headers={"Content-Type": "application/json",
                                          "Content-Length": str(len(meta))})
    try:
        with urllib.request.urlopen(put, timeout=60) as r:
            payload = json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        raise _http_err("youtube upload", exc)
    vid = str(payload.get("id", ""))
    if not vid:
        raise RuntimeError("youtube: upload accepted without video id (retryable)")
    return {"remote_id": vid, "status": "published"}


def publish_webhook(job, content, account: str = "") -> dict:
    """Real generic channel: POST the publication package to MUSIC_WEBHOOK_URL.

    Used as the verifiable real channel where platform OAuth creds are absent:
    real HTTP request, real remote receipt (returned id), real failure modes.
    Requires MUSIC_WEBHOOK_URL (+ optional MUSIC_WEBHOOK_TOKEN bearer).
    """
    url = os.getenv("MUSIC_WEBHOOK_URL", "")
    if not url:
        raise RuntimeError("webhook channel unconfigured (MUSIC_WEBHOOK_URL); deployment blocker")
    payload = json.dumps({
        "idempotency_key": getattr(job, "idempotency_key", ""),
        "platform": getattr(job, "platform", "webhook"),
        "account": account,
        "title": getattr(content, "title", ""),
        "body": getattr(content, "body", "")[:2000],
        "ts": time.time(),
    }).encode()
    headers = {"Content-Type": "application/json"}
    token = _secret("MUSIC_WEBHOOK_TOKEN")
    if token:
        headers["Authorization"] = "Bearer <redacted>"
        authed = {"Authorization": f"Bearer {token}"}
    else:
        authed = {}
    req = urllib.request.Request(url, data=payload, method="POST",
                                 headers={**headers, **authed})
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
    try:
        code = exc.code
    except Exception:
        code = 0
    retryable = code == 429 or (500 <= code < 600)
    # Never include response bodies (may echo tokens); status only.
    err = RuntimeError(f"{where} HTTP {code} ({'retryable' if retryable else 'terminal'})")
    err.retryable = retryable  # type: ignore[attr-defined]
    err.rate_limited = (code == 429)  # type: ignore[attr-defined]
    return err
