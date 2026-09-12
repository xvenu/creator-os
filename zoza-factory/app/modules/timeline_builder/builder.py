"""Timeline intelligence: visuals ↔ narration sync.

Guarantee: video length matches narration length. Scene durations are
allocated proportional to narration weight, then normalized to exactly
`length_seconds`. Gaps (scenes without usable visuals), overrun and
underrun are detected and reported — overrun/underrun are always zero
after normalization by construction.
"""
from __future__ import annotations

import re

MIN_SCENE_SECONDS = 2.0


def sentences(narration: str) -> list[str]:
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", narration.strip()) if s.strip()]
    return parts or ([narration.strip()] if narration.strip() else [])


def build(narration: str, length_seconds: float,
          assets: list[dict] | None = None) -> dict:
    assets = assets or []
    sents = sentences(narration)
    total_words = sum(len(s.split()) for s in sents) or 1

    # Raw allocation proportional to word count, floored at MIN_SCENE_SECONDS.
    raw = [max(MIN_SCENE_SECONDS, length_seconds * len(s.split()) / total_words)
           for s in sents]
    scale = length_seconds / sum(raw) if sum(raw) else 1.0

    scenes, cursor = [], 0.0
    for i, (sent, r) in enumerate(zip(sents, raw)):
        dur = round(r * scale, 2)
        # Last scene absorbs rounding drift so the total is exact.
        if i == len(sents) - 1:
            dur = round(length_seconds - cursor, 2)
        asset = assets[i % len(assets)] if assets else None
        scenes.append({
            "scene_number": i + 1,
            "narration": sent,
            "start_seconds": round(cursor, 2),
            "end_seconds": round(cursor + dur, 2),
            "duration_seconds": dur,
            "asset": (asset or {}).get("source", ""),
            "asset_kind": (asset or {}).get("kind", "none"),
            "status": "covered" if asset else "gap",
        })
        cursor += dur

    total = round(sum(s["duration_seconds"] for s in scenes), 2)
    gaps = [s["scene_number"] for s in scenes if s["status"] == "gap"]
    subtitles_srt = _to_srt(scenes)

    return {
        "total_seconds": total,
        "matches_narration": total == round(length_seconds, 2),
        "scenes": scenes,
        "subtitles_srt": subtitles_srt,
        "gaps": gaps,
        "gap_count": len(gaps),
        "overrun_seconds": 0.0,
        "underrun_seconds": 0.0,
        "scene_count": len(scenes),
    }


def _to_srt(scenes: list[dict]) -> str:
    blocks = []
    for s in scenes:
        blocks.append(
            f"{s['scene_number']}\n"
            f"{_ts(s['start_seconds'])} --> {_ts(s['end_seconds'])}\n"
            f"{s['narration']}\n")
    return "\n".join(blocks)


def _ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
