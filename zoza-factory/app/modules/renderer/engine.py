"""Rendering system: assembly → subtitles → voice → rendering → exports.

Default production path is REAL media (local ffmpeg provider): H.264 MP4 +
AAC audio + muxed subtitles + JPG thumbnail, QC-probed (never trusted from
sidecars). `simulated-test-only` exists solely as an explicitly named test
provider and is never the default. There is NO publishing code path in this
module by design.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

PROVIDERS = {
    "render": [{"name": "local-ffmpeg", "available": True},
               {"name": "runpod-gpu", "available": False},
               {"name": "simulated-test-only", "available": True}],
    "voice": [{"name": "synth-tone-bed", "available": True}],
    "assets": [{"name": "factory-catalog", "available": True},
               {"name": "factory-synthetic", "available": True}],
}


def provider_availability() -> dict:
    try:
        from app.modules.renderer import providers as prov
        dyn = {p["name"]: p for p in prov.available() if "ffmpeg" in p["name"] or "runpod" in p["name"] or "simulated" in p["name"]}
        render = []
        for p in PROVIDERS["render"]:
            entry = dict(p)
            if p["name"] in dyn:
                entry.update(dyn[p["name"]])
            render.append({"name": entry["name"], "available": entry["available"]})
        base = {kind: [{"name": p["name"], "available": p["available"]} for p in plist]
                for kind, plist in PROVIDERS.items()}
        base["render"] = render
        return base
    except Exception:
        return {kind: [{"name": p["name"], "available": p["available"]} for p in plist]
                for kind, plist in PROVIDERS.items()}


def assemble(request_id: str, timeline: dict, voice: dict, output_dir: str) -> dict:
    """Write assembly manifest + subtitles + voice track descriptor."""
    out = Path(output_dir) / request_id
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "request_id": request_id,
        "content_type": timeline.get("content_type", "video"),
        "structure": timeline.get("structure", "beats"),
        "render_profile": timeline.get("render_profile", "local-ffmpeg"),
        "render_width": timeline.get("render_width", 1280),
        "render_height": timeline.get("render_height", 720),
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


def render_video(request_id: str, timeline: dict, output_dir: str,
                 voice: dict | None = None, provider_name: str = "",
                 resolution: tuple[int, int] | None = None) -> dict:
    """Render real media via the configured provider (default local-ffmpeg)."""
    from app.modules.renderer import providers as prov
    voice = voice or {}
    subtitles_srt = timeline.get("subtitles_srt", "") or ""
    if resolution is None:
        resolution = (int(timeline.get("render_width", 1280)),
                      int(timeline.get("render_height", 720)))
    provider = prov.select(provider_name)
    result = provider.render(request_id, timeline, voice, output_dir,
                             resolution, subtitles_srt)
    result["render_profile"] = timeline.get("render_profile", provider.name)
    result["content_type"] = timeline.get("content_type", "video")
    return result


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


def file_record(path: str) -> dict:
    """Storage descriptor: location + checksum + size (no trust, just facts)."""
    p = Path(path)
    raw = p.read_bytes()
    return {"location": str(p.resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw)}


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
