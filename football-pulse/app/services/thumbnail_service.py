"""ThumbnailStrategyService: click concepts (text, visuals, emotion, color).

No image generation in Phase 4 — concepts only, ready for Phase 5 rendering.
"""
from __future__ import annotations

import re

EMOTIONAL_TRIGGERS = ("shock", "curiosity", "triumph", "controversy", "urgency", "joy")

COLOR_STRATEGIES = {
    "shock": {"background": "fiery red", "text": "bold yellow", "accent": "black contrast"},
    "curiosity": {"background": "deep blue", "text": "white", "accent": "neon question mark"},
    "triumph": {"background": "gold gradient", "text": "black", "accent": "confetti"},
    "controversy": {"background": "split red/black", "text": "white caps", "accent": "VS divider"},
    "urgency": {"background": "black", "text": "red alert", "accent": "breaking banner"},
    "joy": {"background": "bright green", "text": "white", "accent": "star burst"},
}

TRIGGER_BY_FORMAT = {
    "breaking_news": "urgency",
    "transfer_update": "shock",
    "match_review": "triumph",
    "match_preview": "curiosity",
    "prediction_report": "curiosity",
    "tactical_breakdown": "curiosity",
    "football_story": "joy",
    "mini_documentary": "curiosity",
}


def thumbnail_text(topic: str, max_words: int = 5) -> str:
    """Punchy ≤5-word overlay: strongest capitalized words, uppercased."""
    words = [w.strip(",.!?") for w in topic.split() if len(w.strip(",.!?")) > 2]
    picked = words[:max_words] or [topic]
    text = " ".join(picked).upper()
    return text[:40]


def visual_elements(topic: str, content_format: str, entities: dict) -> list[str]:
    elements = ["player close-up, intense expression", "bold overlay text, left third"]
    clubs = (entities or {}).get("clubs", [])
    if clubs:
        elements.append(f"{clubs[0].title()} badge colors as backdrop")
    if content_format in ("match_preview", "match_review", "prediction_report"):
        elements.append("split-screen faceoff layout")
    if content_format == "transfer_update":
        elements.append("done-deal handshake motif + jersey swap graphic")
    if content_format == "breaking_news":
        elements.append("'BREAKING' banner, top edge")
    return elements


def click_probability(trigger: str, text: str, urgency: str) -> float:
    """Heuristic 0..1 CTR proxy: trigger weight + brevity + urgency."""
    trigger_w = {"shock": 0.85, "urgency": 0.85, "controversy": 0.8,
                 "curiosity": 0.75, "triumph": 0.7, "joy": 0.65}.get(trigger, 0.6)
    brevity = 1.0 if len(text.split()) <= 4 else 0.8
    urgency_w = {"critical": 1.0, "high": 0.9, "medium": 0.75, "low": 0.6}.get(urgency, 0.7)
    return round(min(trigger_w * 0.5 + brevity * 0.25 + urgency_w * 0.25, 0.97), 3)


def generate_thumbnail(topic: str, content_format: str = "football_story",
                       entities: dict | None = None, urgency: str = "medium") -> dict:
    trigger = TRIGGER_BY_FORMAT.get(content_format, "curiosity")
    text = thumbnail_text(topic)
    return {
        "thumbnail_text": text,
        "visual_elements": visual_elements(topic, content_format, entities or {}),
        "emotional_trigger": trigger,
        "color_strategy": COLOR_STRATEGIES[trigger],
        "click_probability": click_probability(trigger, text, urgency),
    }
