"""Zoza factory client: reachability, submission, state polling, export collection.

Exchange surface is job JSON files in the factory jobs/ dir (audited
read-only schema). Factory internals are never imported. All failures are
returned as status dicts — never raised — so dispatch stays retryable.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from app.modules.zoza_client.config import factory_jobs_dir, zoza_dir

# Factory JobState → client request state.
FACTORY_TO_CLIENT = {
    "QUEUED": "queued",
    "PLANNED": "rendering",
    "AUDIO_READY": "rendering",
    "ASSETS_GENERATING": "rendering",
    "ASSETS_READY": "rendering",
    "ASSEMBLING": "rendering",
    "RENDERED": "rendered",
    "AWAITING_REVIEW": "rendered",
    "APPROVED": "rendered",
    "PUBLISHING": "rendered",  # factory must not publish for football; still an export
    "DELIVERED": "rendered",  # same: treat output as export, flag in metadata
    "FAILED": "failed",
}

CLIENT_STATES = ("created", "submitted", "queued", "rendering",
                 "rendered", "exported", "failed")


def map_factory_state(factory_state: str) -> str:
    return FACTORY_TO_CLIENT.get(str(factory_state), "queued")


def validate_export(payload: dict) -> dict:
    """Local mirror of creator-os shared/contracts.py::validate_export.

    Kept in-pulse (no parent import) so the pulse stays independently
    buildable; semantics must match the shared contract.
    """
    required = ("job_id", "status", "video_path", "thumbnail_path", "metadata")
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(f"export missing fields: {missing}")
    if payload["status"] != "rendered":
        raise ValueError("export status must be 'rendered' (factory never publishes)")
    if not isinstance(payload["metadata"], dict):
        raise ValueError("export metadata must be an object")
    return payload


class ZozaFactory:
    """Thin file-queue client over the factory jobs directory."""

    def __init__(self, jobs_dir: str | None = None) -> None:
        self.jobs_dir = jobs_dir if jobs_dir is not None else factory_jobs_dir()

    def ping(self) -> dict:
        zdir = zoza_dir()
        reachable = bool(self.jobs_dir) and Path(self.jobs_dir).is_dir()
        return {"factory": "zoza-video-factory", "dir": zdir or "not-found",
                "reachable": reachable}

    def _job_path(self, zoza_job_id: str) -> Path:
        return Path(self.jobs_dir) / f"{zoza_job_id}.json"

    def submit(self, job: dict) -> dict:
        """Write job JSON into the factory queue. Idempotent on job_id."""
        if not self.jobs_dir or not Path(self.jobs_dir).is_dir():
            return {"ok": False, "status": "unreachable", "error": "factory jobs dir not found"}
        if not job.get("job_id"):
            return {"ok": False, "status": "failed", "error": "job missing job_id"}
        path = self._job_path(job["job_id"])
        if path.exists():
            return {"ok": True, "status": "submitted", "zoza_job_id": job["job_id"],
                    "reused": True, "path": str(path)}
        try:
            path.write_text(json.dumps(job, indent=2), encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "status": "failed", "error": str(exc)}
        return {"ok": True, "status": "submitted", "zoza_job_id": job["job_id"],
                "reused": False, "path": str(path)}

    def read_job(self, zoza_job_id: str) -> dict | None:
        path = self._job_path(zoza_job_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def poll(self, zoza_job_id: str) -> dict:
        """Current client-side state for a submitted job."""
        job = self.read_job(zoza_job_id)
        if job is None:
            return {"zoza_job_id": zoza_job_id, "state": "submitted",
                    "detail": "job file not yet visible"}
        return {"zoza_job_id": zoza_job_id,
                "state": map_factory_state(job.get("state", "QUEUED")),
                "factory_state": job.get("state"),
                "updated_at": job.get("updated_at", 0)}

    def collect_export(self, zoza_job_id: str) -> dict:
        """Build a contract-validated export from a rendered factory job."""
        job = self.read_job(zoza_job_id)
        if job is None:
            return {"ok": False, "error": "job not found"}
        state = map_factory_state(job.get("state", "QUEUED"))
        if state != "rendered":
            return {"ok": False, "error": f"job not rendered (factory state: {job.get('state')})"}
        output_dir = Path(self.jobs_dir).parent / "output" / zoza_job_id
        video_path = job.get("video_path") or _first_media(output_dir, (".mp4", ".mov", ".mkv"))
        thumbnail_path = job.get("thumbnail_path") or _first_media(output_dir, (".png", ".jpg"))
        export = {"job_id": zoza_job_id, "status": "rendered",
                  "video_path": video_path, "thumbnail_path": thumbnail_path,
                  "metadata": {"title": job.get("title", ""), "description": job.get("description", ""),
                               "hashtags": job.get("hashtags", []),
                               "source_package": (job.get("meta") or {}).get("package_id", ""),
                               "factory_state": job.get("state")}}
        try:
            validate_export(export)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        if not video_path or not os.path.exists(video_path):
            return {"ok": False, "error": "rendered video file not present"}
        if not thumbnail_path or not os.path.exists(thumbnail_path):
            return {"ok": False, "error": "export thumbnail not present"}
        return {"ok": True, "export": export}


def _first_media(directory: Path, suffixes: tuple[str, ...]) -> str | None:
    if not directory.is_dir():
        return None
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() in suffixes and path.is_file():
            return str(path)
    return None
