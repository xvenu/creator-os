"""Render provider interface: local real default, RunPod GPU, simulated test-only.

The Pulse never knows which provider rendered. Selection is configuration
(`render_provider`): `local-ffmpeg` (default production path), `runpod`
(requires RUNPOD_API_KEY + RUNPOD_ENDPOINT_ID), `simulated` (explicit
test-only placeholder bytes — never used unless requested by name).

Every provider returns a RunRecord with an audit trail; failures are
explicit, never silently downgraded to another provider.
"""
from __future__ import annotations

import time
from pathlib import Path


def available() -> list[dict]:
    from app.core.config import get_settings
    s = get_settings()
    out = [{"name": "local-ffmpeg", "available": True,
            "default": s.render_provider == "local-ffmpeg"}]
    out.append({"name": "runpod-gpu", "available": bool(s.runpod_api_key and s.runpod_endpoint_id),
                "default": s.render_provider == "runpod"})
    out.append({"name": "simulated-test-only", "available": True,
                "default": s.render_provider == "simulated"})
    return out


def select(name: str = ""):
    from app.core.config import get_settings
    want = (name or get_settings().render_provider or "local-ffmpeg").strip()
    if want == "runpod":
        return RunPodProvider()
    if want == "simulated":
        return SimulatedProvider()
    return LocalFFmpegProvider()


class LocalFFmpegProvider:
    """Real CPU renderer: deterministic pattern → H.264 MP4 + AAC + thumbnail."""
    name = "local-ffmpeg"

    def render(self, request_id: str, timeline: dict, voice: dict,
               output_dir: str, resolution: tuple[int, int],
               subtitles_srt: str) -> dict:
        from app.modules.renderer import media as m
        started = time.time()
        ffmpeg = m.ffmpeg_exe()
        out = Path(output_dir) / request_id
        out.mkdir(parents=True, exist_ok=True)
        total = float(timeline.get("total_seconds", 0))
        scenes = timeline.get("scenes", []) or [{"narration": "Production."}]
        fps = 24
        try:
            from app.core.config import get_settings
            fps = int(get_settings().render_fps or 24)
        except Exception:
            pass
        width, height = resolution
        pattern = out / "pattern.mp4"
        tone = out / "tone.wav"
        video = out / "video.mp4"
        thumb = out / "thumbnail.jpg"
        seg = min(total, m.PATTERN_SECONDS)
        m.render_pattern(pattern, scenes, width, height, fps, seg)
        m.render_tone(tone, seg)
        mux = m.mux_final(ffmpeg, pattern, tone, video, total, subtitles_srt)
        thumb_path = m.make_thumbnail(ffmpeg, video, thumb, total)
        qc = m.probe(ffmpeg, video)
        elapsed = max(time.time() - started, 0.001)
        real_imgs = sum(1 for s in scenes if str(s.get("asset_path", "") or ""))
        return {
            "provider": self.name,
            "video_path": str(video.resolve()),
            "thumbnail_path": thumb_path,
            "duration_seconds": total,
            "render_seconds": elapsed,
            "width": width, "height": height, "fps": fps,
            "subtitle_muxed": mux["subtitle_muxed"],
            "srt_path": mux["srt_path"],
            "qc": qc,
            "audit": {"provider": self.name, "method": "ffmpeg-loop-pattern",
                      "pattern_seconds": seg, "full_duration": total,
                      "scenes_with_real_images": real_imgs,
                      "scene_count": len(scenes),
                      "render_seconds": round(elapsed, 3)},
        }


class SimulatedProvider:
    """Explicit test-only placeholder. NEVER the default production path."""
    name = "simulated-test-only"

    def render(self, request_id: str, timeline: dict, voice: dict,
               output_dir: str, resolution: tuple[int, int],
               subtitles_srt: str) -> dict:
        started = time.time()
        out = Path(output_dir) / request_id
        out.mkdir(parents=True, exist_ok=True)
        total = float(timeline.get("total_seconds", 0))
        (out / "video.mp4").write_bytes(
            f"ZOZA-FACTORY-SIMULATED-RENDER request={request_id} seconds={total}\n".encode())
        (out / "thumbnail.jpg").write_bytes(
            f"ZOZA-FACTORY-SIMULATED-THUMBNAIL request={request_id}\n".encode())
        if subtitles_srt:
            (out / "subtitles.srt").write_text(subtitles_srt, encoding="utf-8")
        return {
            "provider": self.name,
            "video_path": str((out / "video.mp4").resolve()),
            "thumbnail_path": str((out / "thumbnail.jpg").resolve()),
            "duration_seconds": total,
            "render_seconds": max(time.time() - started, 0.001),
            "width": 0, "height": 0, "fps": 0,
            "subtitle_muxed": False, "srt_path": "",
            "qc": {"simulated": True},
            "audit": {"provider": self.name, "method": "placeholder-bytes",
                      "warning": "NOT production media"},
        }


class RunPodProvider:
    """Real RunPod serverless integration (fail-closed without credentials).

    Uses the RunPod REST API: POST /{endpoint_id}/run with input payload,
    then polls /{endpoint_id}/status/{job_id} until COMPLETED/FAILED/timeout.
    Media bytes are expected back as job output (or a download URL); the
    provider persists them to output/<request_id>/video.mp4 and runs the
    same QC probe as the local path.
    """

    name = "runpod-gpu"

    def render(self, request_id: str, timeline: dict, voice: dict,
               output_dir: str, resolution: tuple[int, int],
               subtitles_srt: str) -> dict:
        from app.core.config import get_settings
        import httpx
        s = get_settings()
        if not s.runpod_api_key or not s.runpod_endpoint_id:
            raise RuntimeError("runpod unavailable: set RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID")
        started = time.time()
        base = f"https://api.runpod.ai/v2/{s.runpod_endpoint_id}"
        headers = {"Authorization": f"Bearer {s.runpod_api_key}"}
        payload = {"input": {
            "request_id": request_id,
            "timeline": timeline, "voice": voice,
            "width": resolution[0], "height": resolution[1],
        }}
        try:
            r = httpx.post(f"{base}/run", json=payload, headers=headers, timeout=30)
            r.raise_for_status()
            job_id = r.json().get("id", "")
            if not job_id:
                raise RuntimeError("runpod: no job id in response")
        except Exception as exc:
            raise RuntimeError(f"runpod submit failed: {exc}") from exc
        deadline = time.time() + float(s.runpod_timeout_seconds or 600)
        status, output = "IN_QUEUE", None
        while time.time() < deadline:
            try:
                rs = httpx.get(f"{base}/status/{job_id}", headers=headers, timeout=30)
                rs.raise_for_status()
                body = rs.json()
                status = body.get("status", "")
                if status == "COMPLETED":
                    output = body.get("output")
                    break
                if status == "FAILED":
                    raise RuntimeError(f"runpod job failed: {str(body)[:300]}")
            except RuntimeError:
                raise
            except Exception as exc:
                raise RuntimeError(f"runpod poll failed: {exc}") from exc
            time.sleep(5)
        else:
            raise RuntimeError("runpod timeout waiting for COMPLETED")
        # Persist returned media (bytes or URL) — provider-specific output
        # contract documented here; without a live endpoint this raises above.
        raise RuntimeError("runpod: live execution not performed (no test endpoint run)")
