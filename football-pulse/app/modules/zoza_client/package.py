"""Package builder: content package → Zoza job JSON.

FootballPulse emits exactly one handoff shape (the package spec). The
factory receives a Zoza-native job document; publish_targets is always
empty — Zoza never publishes.
"""
from __future__ import annotations

import re
import time

REQUIRED_PACKAGE_FIELDS = ("package_id", "title", "summary", "script",
                           "visual_requirements", "voice_requirements",
                           "target_platform", "priority")


def build_zoza_package(content: dict) -> dict:
    """Normalize a Phase 4 content package into the Zoza handoff package."""
    missing = [k for k in ("package_id", "title") if not content.get(k)]
    if missing:
        raise ValueError(f"package missing fields: {missing}")
    script = content.get("script") or {}
    if isinstance(script, dict):
        narration = " ".join(
            str(script.get(k, "")) for k in ("hook", "body", "outro")).strip()
    else:
        narration = str(script)
    if not narration:
        raise ValueError("package script is empty")
    seo = content.get("seo") or {}
    if isinstance(content.get("priority"), (int, float)):
        priority = int(content["priority"])
    else:
        opportunity = content.get("opportunity_score", 0) or 0
        priority = int(float(opportunity) * 100)
    return {
        "package_id": str(content["package_id"]),
        "title": str(content["title"]),
        "summary": str(content.get("summary", content.get("topic", ""))),
        "script": narration,
        "visual_requirements": list(content.get("visual_requirements")
                                    or content.get("target_regions", [])),
        "voice_requirements": dict(content.get("voice_requirements", {}) or {
            "language": content.get("language", "en"),
            "regions": content.get("target_regions", []),
        }),
        "target_platform": str(content.get("target_platform")
                               or ",".join(content.get("platform_targets", ["youtube"]))),
        "priority": priority,
        "hashtags": list(seo.get("hashtags", [])),
        "aspect_ratio": str(content.get("aspect_ratio", "16:9")),
    }


def _split_scenes(narration: str, max_scenes: int = 8) -> list[dict]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", narration.strip()) if s.strip()]
    groups: list[list[str]] = []
    per = max(1, -(-len(sentences) // max_scenes))  # ceil division
    for i in range(0, len(sentences), per):
        groups.append(sentences[i:i + per])
    return [{"scene_number": n, "narration": " ".join(g), "status": "PENDING"}
            for n, g in enumerate(groups[:max_scenes], 1)]


def to_zoza_job(package: dict, job_prefix: str = "fp") -> dict:
    """Package → Zoza-native job document (audited read-only schema)."""
    for field in REQUIRED_PACKAGE_FIELDS:
        if field not in package:
            raise ValueError(f"package missing field: {field}")
    now = time.time()
    return {
        "job_id": f"{job_prefix}-{package['package_id'][:8]}",
        "title": package["title"],
        "description": package["summary"],
        "hashtags": package.get("hashtags", []),
        "aspect_ratio": package.get("aspect_ratio", "16:9"),
        "content_type": "football",
        "series_id": None,
        "episode_number": None,
        "voiceover_script": package["script"],
        "voice_style": str(package.get("voice_requirements", {}).get("style", "energetic")),
        "scenes": _split_scenes(package["script"]),
        "background_music_vibe": "",
        "voice_id_override": package.get("voice_requirements", {}).get("voice_id"),
        "state": "QUEUED",
        "include_music": False,
        "music": {"source": "none", "track_id": None, "prompt": "", "volume_db": -14.0},
        "characters": [],
        "publish_targets": [],  # factory never publishes
        "approved_at": None,
        "created_at": now,
        "updated_at": now,
        "telegram_message_id": None,
        "meta": {"source": "football-pulse", "package_id": package["package_id"],
                 "priority": package["priority"],
                 "target_platform": package["target_platform"],
                 "visual_requirements": package["visual_requirements"]},
    }
