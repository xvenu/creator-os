"""Real media synthesis + inspection for the factory's local provider.

Production path (default): deterministic PIL/numpy frames → H.264 MP4 via a
real ffmpeg binary (imageio-ffmpeg bundle), PCM narration tone → AAC, SRT
subtitles muxed as mov_text when possible, JPG thumbnail, ffprobe-style QC by
parsing `ffmpeg -i` output plus file-signature checks.

Long durations are produced by looping a short deterministic pattern segment
(`-stream_loop` + `-t`), so a 3h movie has a correct container/duration
without rendering 250k unique frames. The pattern content still reflects the
scene plan (colors/roles), and metadata records the method honestly.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import subprocess
import time
import wave
from pathlib import Path

FPS_DEFAULT = 24
PATTERN_SECONDS = 6.0

# Deterministic palette per scene index (broadcast-safe solids).
PALETTE = [
    (23, 32, 48), (58, 41, 76), (29, 74, 74), (76, 53, 29),
    (46, 74, 29), (74, 29, 52), (35, 55, 90), (90, 35, 35),
]


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("ffmpeg binary unavailable (install imageio-ffmpeg)") from exc


def resolution_for(aspect_ratio: str, resolution: str, content_type: str) -> tuple[int, int]:
    ar = (aspect_ratio or "16:9").strip()
    if ar == "9:16":
        base = (720, 1280)
    elif ar == "1:1":
        base = (720, 720)
    elif ar == "21:9":
        base = (1680, 720)
    else:
        base = (1280, 720)
    res = (resolution or "1080p").strip().lower()
    if res == "4k":
        scale = 2.0 if base[0] <= 1280 else 1.2
        w, h = int(base[0] * scale) // 2 * 2, int(base[1] * scale) // 2 * 2
        return (w, h)
    if res == "720p":
        return base
    return base  # 1080p default maps to the 720p-height working raster


def _scene_color(i: int) -> tuple[int, int, int]:
    return PALETTE[i % len(PALETTE)]


def render_pattern(pattern_mp4: Path, scenes: list[dict], width: int, height: int,
                   fps: int, pattern_seconds: float) -> dict:
    """Render the deterministic pattern segment (no audio).

    Scenes carrying `asset_path` to a decodable local image use that real
    image as the frame background (center-crop); otherwise a deterministic
    solid is synthesized. Every frame therefore decodes real image bytes
    whenever the acquisition layer supplied real files.
    """
    import numpy as np
    from PIL import Image, ImageDraw
    import imageio.v2 as imageio

    total_frames = max(1, int(round(pattern_seconds * fps)))
    n = max(1, len(scenes))
    cache: dict[str, object] = {}
    writer = imageio.get_writer(
        str(pattern_mp4), fps=fps, codec="libx264", quality=8,
        macro_block_size=None,
        ffmpeg_params=["-pix_fmt", "yuv420p", "-preset", "veryfast"],
    )
    try:
        for f in range(total_frames):
            scene_idx = (f * n) // total_frames
            scene = scenes[scene_idx] if scene_idx < len(scenes) else {}
            img = _background(cache, str(scene.get("asset_path", "") or ""),
                              width, height, _scene_color(scene_idx))
            draw = ImageDraw.Draw(img)
            # Deterministic overlay: scene index + progress bar (no fonts needed).
            bar_w = int(width * (f + 1) / total_frames)
            draw.rectangle([0, height - 12, bar_w, height], fill=(255, 255, 255))
            draw.rectangle([10, 10, 10 + 8 * ((scene_idx % 8) + 1), 22], fill=(255, 255, 255))
            writer.append_data(np.asarray(img))
    finally:
        writer.close()
    return {"frames": total_frames, "fps": fps, "width": width, "height": height}


def _background(cache: dict, path: str, width: int, height: int,
                fallback: tuple[int, int, int]):
    from PIL import Image
    if path:
        try:
            if path not in cache:
                im = Image.open(path).convert("RGB")
                # Center-crop to target aspect, then resize.
                tr, sr = width / height, im.width / im.height
                if sr > tr:
                    nw = int(im.height * tr)
                    x0 = (im.width - nw) // 2
                    im = im.crop((x0, 0, x0 + nw, im.height))
                else:
                    nh = int(im.width / tr)
                    y0 = (im.height - nh) // 2
                    im = im.crop((0, y0, im.width, y0 + nh))
                cache[path] = im.resize((width, height))
            return cache[path].copy()
        except Exception:
            pass
    return Image.new("RGB", (width, height), fallback)


def render_tone(tone_wav: Path, seconds: float, sample_rate: int = 44100) -> dict:
    """Deterministic narration-bed tone (sine 220+440Hz mix, -20dBFS)."""
    import struct
    n = max(1, int(seconds * sample_rate))
    amp = int(32767 * 0.1)
    with wave.open(str(tone_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        for i in range(n):
            t = i / sample_rate
            v = int(amp * (0.6 * math.sin(2 * math.pi * 220 * t)
                           + 0.4 * math.sin(2 * math.pi * 440 * t)))
            w.writeframes(struct.pack("<h", v))
    return {"seconds": seconds, "sample_rate": sample_rate}


def mux_final(ffmpeg: str, pattern_mp4: Path, tone_wav: Path, out_mp4: Path,
              duration: float, subtitles_srt: str) -> dict:
    """Loop pattern+audio to the exact duration, mux audio, then subtitles."""
    loops_v = max(1, math.ceil(duration / PATTERN_SECONDS))
    tmp_av = out_mp4.with_name(out_mp4.stem + ".av.mp4")
    cmd = [ffmpeg, "-y",
           "-stream_loop", str(loops_v), "-i", str(pattern_mp4),
           "-stream_loop", str(loops_v), "-i", str(tone_wav),
           "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
           "-t", f"{duration:.2f}", "-movflags", "+faststart",
           str(tmp_av)]
    _run(cmd)
    subtitle_muxed = False
    srt_path = out_mp4.with_name(out_mp4.stem + ".srt")
    srt_path.write_text(subtitles_srt or "", encoding="utf-8")
    final_path = out_mp4
    if subtitles_srt and subtitles_srt.strip():
        tr = out_mp4.with_name(out_mp4.stem + ".sub.mp4")
        r = _run([ffmpeg, "-y", "-i", str(tmp_av), "-i", str(srt_path),
                  "-c", "copy", "-c:s", "mov_text", str(tr)], check=False)
        if r == 0 and tr.exists():
            final_path = tr
            subtitle_muxed = True
    if final_path != out_mp4:
        if out_mp4.exists():
            out_mp4.unlink()
        final_path.rename(out_mp4)
    try:
        tmp_av.unlink(missing_ok=True)
    except Exception:
        pass
    return {"subtitle_muxed": subtitle_muxed, "srt_path": str(srt_path)}


def make_thumbnail(ffmpeg: str, video_mp4: Path, thumb_jpg: Path, duration: float) -> str:
    ts = min(1.0, max(0.2, duration / 2))
    r = _run([ffmpeg, "-y", "-ss", f"{ts:.2f}", "-i", str(video_mp4),
              "-vframes", "1", "-q:v", "4", str(thumb_jpg)], check=False)
    if r == 0 and thumb_jpg.exists():
        return str(thumb_jpg.resolve())
    # Fallback: deterministic solid thumbnail via PIL.
    from PIL import Image
    Image.new("RGB", (640, 360), (23, 32, 48)).save(str(thumb_jpg), "JPEG")
    return str(thumb_jpg.resolve())


def probe(ffmpeg: str, video_mp4: Path) -> dict:
    """Inspect media via `ffmpeg -i` stderr + file signature. No sidecar trust."""
    p = subprocess.run([ffmpeg, "-i", str(video_mp4)],
                       capture_output=True, text=True, timeout=60)
    info = p.stderr or ""
    out: dict = {"ffprobe_text": info[-2000:]}
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", info)
    out["duration_seconds"] = (int(m.group(1)) * 3600 + int(m.group(2)) * 60
                               + float(m.group(3))) if m else 0.0
    mv = re.search(r"Video:\s*([a-z0-9]+)", info)
    mres = re.search(r"(\d{3,5})x(\d{3,5})", info)
    mfps = re.search(r"(\d+(?:\.\d+)?)\s*fps", info)
    out.update({"video_codec": mv.group(1) if mv else "",
                "width": int(mres.group(1)) if mres else 0,
                "height": int(mres.group(2)) if mres else 0,
                "fps": float(mfps.group(1)) if mfps else 0.0})
    ma = re.search(r"Audio:\s*([a-z0-9]+)", info)
    out["audio_codec"] = ma.group(1) if ma else ""
    ms = re.search(r"Subtitle:\s*([a-z0-9_]+)", info)
    out["subtitle_codec"] = ms.group(1) if ms else ""
    raw = video_mp4.read_bytes()
    out["size_bytes"] = len(raw)
    out["ftyp_present"] = len(raw) > 8 and raw[4:8] == b"ftyp"
    out["sha256"] = hashlib.sha256(raw).hexdigest()
    return out


def qc_report(qc: dict, expect: dict) -> dict:
    dur_ok = abs(qc.get("duration_seconds", 0) - expect["duration"]) <= 1.0
    res_ok = (qc.get("width") == expect["width"] and qc.get("height") == expect["height"])
    checks = {
        "container_ftyp": bool(qc.get("ftyp_present")),
        "video_stream": qc.get("video_codec", "") in ("h264", "avc"),
        "audio_stream": qc.get("audio_codec", "") in ("aac", "mp3", "opus", "ac3"),
        "duration": dur_ok,
        "resolution": res_ok,
        "size_nonzero": qc.get("size_bytes", 0) > 10_000,
    }
    if expect.get("subtitle_expected"):
        checks["subtitle"] = bool(qc.get("subtitle_codec"))
    return {"checks": checks, "passed": all(checks.values()), "qc": qc}


def _run(cmd: list[str], check: bool = True) -> int:
    started = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if check and p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd[:6])}…: {(p.stderr or '')[-500:]}")
    return p.returncode
