"""Storage abstraction: local filesystem (dev/test) + S3-compatible (production).

Pulse logic never changes: `place()` returns a descriptor with location,
checksum, size, and backend. S3 upload is attempted only when
`storage_backend=s3` AND bucket + credentials are configured; otherwise the
export stays local and the descriptor says so honestly.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import time
from pathlib import Path


def place(request_id: str, content_type: str, video_path: str,
          thumb_path: str, output_dir: str) -> dict:
    from app.core.config import get_settings
    s = get_settings()
    video = Path(video_path)
    thumb = Path(thumb_path)
    desc = {
        "backend": "local",
        "request_id": request_id,
        "content_type": content_type,
        "video_location": str(video.resolve()),
        "thumbnail_location": str(thumb.resolve()),
        "video_sha256": _sha(video),
        "thumbnail_sha256": _sha(thumb),
        "video_size": video.stat().st_size if video.exists() else 0,
        "created_at": time.time(),
        "owning_request": request_id,
    }
    if (s.storage_backend or "local").lower() == "s3" and s.storage_s3_bucket:
        try:
            remote = _s3_upload(s, video, thumb, request_id)
            desc.update(remote)
            desc["backend"] = "s3"
        except Exception as exc:
            desc["backend"] = "local"
            desc["s3_error"] = str(exc)[:300]
    return desc


def _sha(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception:
        return ""


def _s3_upload(s, video: Path, thumb: Path, request_id: str) -> dict:
    import boto3  # optional dependency; production images include it
    endpoint = s.storage_s3_endpoint or None
    client = boto3.client("s3", endpoint_url=endpoint)
    prefix = (s.storage_s3_prefix or "zoza-exports/").rstrip("/") + "/"
    vk = f"{prefix}{request_id}/video.mp4"
    tk = f"{prefix}{request_id}/thumbnail.jpg"
    client.upload_file(str(video), s.storage_s3_bucket, vk)
    client.upload_file(str(thumb), s.storage_s3_bucket, tk)
    return {"s3_bucket": s.storage_s3_bucket, "s3_video_key": vk,
            "s3_thumbnail_key": tk}
