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
    return build_for_content(narration, length_seconds, assets, content_type="video")


def build_for_content(narration: str, length_seconds: float,
                      assets: list[dict] | None = None,
                      content_type: str | None = "video",
                      call_to_action: str = "") -> dict:
    """Content-aware timeline. Same duration guarantee as build(), plus a
    structural role per scene:

    - movie → three-acts (act-i / act-ii / act-iii)
    - ad → hook-body-cta (first scene hook, last scene cta)
    - anime → cold_open-beats-tag
    - video / ai_film → beats
    """
    assets = assets or []
    sents = sentences(narration)
    # Ads append the CTA as a closing beat when supplied separately.
    cta = (call_to_action or "").strip()
    ct = (content_type or "video").strip().lower()
    if ct == "ad" and cta and all(cta not in s for s in sents):
        sents = [*sents, cta]
    total_words = sum(len(s.split()) for s in sents) or 1

    # Raw allocation proportional to word count, floored at MIN_SCENE_SECONDS.
    raw = [max(MIN_SCENE_SECONDS, length_seconds * len(s.split()) / total_words)
           for s in sents]
    scale = length_seconds / sum(raw) if sum(raw) else 1.0

    scenes, cursor = [], 0.0
    n = len(sents)
    for i, (sent, r) in enumerate(zip(sents, raw)):
        dur = round(r * scale, 2)
        # Last scene absorbs rounding drift so the total is exact.
        if i == n - 1:
            dur = round(length_seconds - cursor, 2)
        asset = assets[i % len(assets)] if assets else None
        scenes.append({
            "scene_number": i + 1,
            "narration": sent,
            "role": _role_for(ct, i, n),
            "start_seconds": round(cursor, 2),
            "end_seconds": round(cursor + dur, 2),
            "duration_seconds": dur,
            "asset": (asset or {}).get("source", ""),
            "asset_kind": (asset or {}).get("kind", "none"),
            "asset_path": (asset or {}).get("path", ""),
            "status": "covered" if asset else "gap",
        })
        cursor += dur

    total = round(sum(s["duration_seconds"] for s in scenes), 2)
    gaps = [s["scene_number"] for s in scenes if s["status"] == "gap"]
    subtitles_srt = _to_srt(scenes)

    return {
        "total_seconds": total,
        "matches_narration": total == round(length_seconds, 2),
        "content_type": ct if ct in ("video", "anime", "movie", "ad", "ai_film") else "video",
        "structure": _structure_for(ct),
        "scenes": scenes,
        "subtitles_srt": subtitles_srt,
        "gaps": gaps,
        "gap_count": len(gaps),
        "overrun_seconds": 0.0,
        "underrun_seconds": 0.0,
        "scene_count": len(scenes),
    }


def _structure_for(content_type: str) -> str:
    return {"movie": "three-acts", "ad": "hook-body-cta",
            "anime": "cold_open-beats-tag"}.get(content_type, "beats")


def _role_for(content_type: str, index: int, total: int) -> str:
    if content_type == "movie" and total > 0:
        frac = index / total
        if frac < 0.25:
            return "act-i-setup"
        if frac < 0.75:
            return "act-ii-confrontation"
        return "act-iii-resolution"
    if content_type == "ad" and total > 0:
        if index == 0:
            return "hook"
        if index == total - 1:
            return "cta"
        return "body"
    if content_type == "anime" and total > 0:
        if index == 0:
            return "cold_open"
        if index == total - 1:
            return "tag"
        return "beat"
    return "beat"


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
