"""Rendering system: assembly → subtitles → voice → rendering → exports.

Simulated renderer (stdlib file writes, no ffmpeg). Real render providers
plug in behind PROVIDERS without changing the pipeline. There is NO
publishing code path in this module by design.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

PROVIDERS = {
    "render": [{"name": "simulated-1080p", "available": True}],
    "voice": [{"name": "simulated-tts", "available": True}],
    "assets": [{"name": "factory-catalog", "available": True}],
}


def provider_availability() -> dict:
    return {kind: [{"name": p["name"], "available": p["available"]} for p in plist]
            for kind, plist in PROVIDERS.items()}


def assemble(request_id: str, timeline: dict, voice: dict, output_dir: str) -> dict:
    """Write assembly manifest + subtitles + voice track descriptor."""
    out = Path(output_dir) / request_id
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "request_id": request_id,
        "scenes": timeline.get("scenes", []),
        "total_seconds": timeline.get("total_seconds", 0),
        "voice": {"profile": voice.get("profile"), "tone": voice.get("tone"),
                  "pacing_wpm": voice.get("pacing_wpm"), "emotion": voice.get("emotion")},
        "assembled_at": time.time(),
    }
    (out / "assembly.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "subtitles.srt").write_text(timeline.get("subtitles_srt", ""),
                                       encoding="utf-8")
    return manifest


def render_video(request_id: str, timeline: dict, output_dir: str) -> dict:
    """Simulated render: deterministic placeholder video + thumbnail files."""
    out = Path(output_dir) / request_id
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    total = float(timeline.get("total_seconds", 0))
    video_path = out / "video.mp4"
    video_path.write_bytes(
        f"ZOZA-FACTORY-SIMULATED-RENDER request={request_id} seconds={total}\n".encode())
    thumb_path = out / "thumbnail.jpg"
    thumb_path.write_bytes(
        f"ZOZA-FACTORY-SIMULATED-THUMBNAIL request={request_id}\n".encode())
    elapsed = max(time.time() - started, 0.001)
    return {"video_path": str(video_path.resolve()), "thumbnail_path": str(thumb_path.resolve()),
            "duration_seconds": total, "render_seconds": elapsed}


def export_package(request_id: str, video_path: str, thumbnail_path: str,
                   metadata: dict, output_dir: str) -> dict:
    """Write the contract-validated export manifest. Never publishes."""
    started = time.time()
    export = {"job_id": request_id, "status": "rendered",
              "video_path": video_path, "thumbnail_path": thumbnail_path,
              "metadata": metadata}
    _validate_export_shape(export)
    out = Path(output_dir) / request_id
    (out / "export.json").write_text(json.dumps(export, indent=2), encoding="utf-8")
    return {"export": export, "export_seconds": max(time.time() - started, 0.001)}


def _validate_export_shape(export: dict) -> dict:
    """Local mirror of shared/contracts.py::validate_export (factory-owned copy
    so the factory stays independently buildable; semantics must match)."""
    required = ("job_id", "status", "video_path", "thumbnail_path", "metadata")
    missing = [k for k in required if k not in export]
    if missing:
        raise ValueError(f"export missing fields: {missing}")
    if export["status"] != "rendered":
        raise ValueError("export status must be 'rendered' (factory never publishes)")
    if not isinstance(export["metadata"], dict):
        raise ValueError("export metadata must be an object")
    return export
