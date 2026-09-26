"""Content-type registry: video / anime / movie / ad / ai_film.

Pulse-agnostic: ANY pulse (present or future) requests one of these
families via Contract V2 `content_type`. Each family declares its
structure, default voice, render profile, and aspect default. Pure data +
pure helpers — no I/O, no publishing.
"""
from __future__ import annotations

REGISTRY: dict[str, dict] = {
    "video": {
        "label": "Video",
        "description": "Generic pulse video (short/mid, real or mixed).",
        "structure": "beats",
        "default_voice": "documentary",
        "default_aspect": "16:9",
        "render_profile": "simulated-1080p",
        "max_length": 3600,
    },
    "anime": {
        "label": "Anime",
        "description": "Stylized animated segment/episode.",
        "structure": "cold_open-beats-tag",
        "default_voice": "anime-dub",
        "default_aspect": "16:9",
        "render_profile": "simulated-anime-1080p",
        "max_length": 3600,
        "preferred_kinds": ["anime_keyframe", "anime_background", "real_photo",
                            "public_domain", "ai_generated"],
    },
    "movie": {
        "label": "Movie",
        "description": "Long-form cinematic output, organized in acts.",
        "structure": "three-acts",
        "default_voice": "cinematic-trailer",
        "default_aspect": "21:9",
        "render_profile": "simulated-cinema-4k",
        "max_length": 10800,
    },
    "ad": {
        "label": "Ad",
        "description": "Short commercial/awareness spot: hook + body + CTA.",
        "structure": "hook-body-cta",
        "default_voice": "commercial",
        "default_aspect": "16:9",
        "render_profile": "simulated-ad-1080p",
        "max_length": 300,
        "preferred_kinds": ["product_shot", "brand_asset", "real_footage",
                            "real_photo", "ai_generated"],
    },
    "ai_film": {
        "label": "AI Film",
        "description": "Fully synthetic short/film (AI generation expected).",
        "structure": "beats",
        "default_voice": "cinematic-trailer",
        "default_aspect": "16:9",
        "render_profile": "simulated-ai-1080p",
        "max_length": 3600,
    },
}


def normalize(content_type: str | None) -> str:
    """Map any input to a known family; unknown → 'video' (fail-open)."""
    ct = (content_type or "video").strip().lower()
    return ct if ct in REGISTRY else "video"


def spec(content_type: str | None) -> dict:
    return REGISTRY[normalize(content_type)]


def families() -> list[str]:
    return list(REGISTRY)


def structure_for(content_type: str | None) -> str:
    return spec(content_type)["structure"]


def default_voice_for(content_type: str | None) -> str:
    return spec(content_type)["default_voice"]


def render_profile_for(content_type: str | None, ai_ratio: float = 0.0) -> str:
    """Render profile is driven by content family; full-AI video falls
    back to the synthetic profile regardless of family."""
    if ai_ratio >= 1.0:
        return "simulated-ai-1080p"
    return spec(content_type)["render_profile"]


def describe() -> list[dict]:
    return [{"family": k, **v} for k, v in REGISTRY.items()]
