"""Factory Contract V2 (CANONICAL, frozen): Pulse sends intent, Zoza decides strategy.

Version: v2. Any incompatible change requires a version bump (v3) and a new
model — never an in-place redefinition. Pulses MUST NOT redefine
ProductionRequestIn/ProductionMode (guardrail-tested on both sides).

Canonical request fields: request_id, pulse, content_type, goal, style,
length_seconds, urgency, production_mode, ai_generation_allowed, sources,
evidence, voice_profile, target_audience, priority (+ additive universal
fields: format_variant, aspect_ratio, resolution, language, narration,
brand_context, call_to_action, asset_requirements).

No publishing fields. No audience-ownership fields. No revenue fields.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

CONTRACT_VERSION = "v2"

CANONICAL_FIELDS = (
    "request_id", "pulse", "content_type", "goal", "style",
    "length_seconds", "urgency", "production_mode", "ai_generation_allowed",
    "sources", "evidence", "voice_profile", "target_audience", "priority",
)

CANONICAL_EXPORT_FIELDS = (
    "job_id", "status", "video_path", "thumbnail_path", "metadata",
)


class ProductionMode(str, Enum):
    REALITY_ONLY = "REALITY_ONLY"
    REALITY_FIRST = "REALITY_FIRST"
    HYBRID = "HYBRID"
    AI_CREATIVE = "AI_CREATIVE"


class Urgency(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    breaking = "breaking"


class ContentType(str, Enum):
    """Universal output family. Orthogonal to ProductionMode.

    - VIDEO: generic pulse video (short/mid, any pulse).
    - ANIME: stylized animated segment/episode.
    - MOVIE: long-form cinematic output (acts).
    - AD: short commercial/awareness spot (hook + CTA).
    - AI_FILM: fully synthetic short/film (expects AI_CREATIVE or
      HYBRID with ai_generation_allowed=True).
    Real vs AI is still decided by ProductionMode; ContentType decides
    structure, pacing, voice default, and render profile.
    """
    VIDEO = "video"
    ANIME = "anime"
    MOVIE = "movie"
    AD = "ad"
    AI_FILM = "ai_film"


CONTENT_TYPES = tuple(t.value for t in ContentType)

# Any pulse may request production. Well-known pulses are listed for
# docs/discovery only — the factory never allow-lists pulses.
KNOWN_PULSES = ("music-pulse", "football-pulse", "anime-pulse",
                "movie-pulse", "ads-pulse")


REQUEST_STATES = ("created", "planned", "acquiring", "assembling",
                  "rendering", "exported", "failed")


class ProductionRequestIn(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    # Pulse origin: free-form so ANY present or future pulse can produce.
    # Never validated against an allow-list (see KNOWN_PULSES, docs only).
    pulse: str = ""
    goal: str = Field(min_length=1)
    style: str = ""
    length_seconds: int = Field(gt=0, le=10800)
    urgency: Urgency = Urgency.normal
    production_mode: ProductionMode = ProductionMode.REALITY_FIRST
    ai_generation_allowed: bool = False
    sources: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    voice_profile: str = ""
    target_audience: str = ""
    priority: int = Field(default=0, ge=0, le=100)
    # Universal factory fields (all optional → backward compatible).
    content_type: ContentType = ContentType.VIDEO
    format_variant: str = ""  # pulse-defined: short|episode|feature|spot|...
    aspect_ratio: str = "16:9"
    resolution: str = "1080p"
    language: str = "en"
    narration: str = ""  # explicit voiceover script (director also accepts goal+evidence fallback)
    brand_context: str = ""  # ads: brand/product line (production only, never revenue)
    call_to_action: str = ""  # ads: closing CTA line
    # Pulse-declared acquisition constraints. Zoza honors them (see director):
    # {"real_media_required": bool, "preferred_types": [category...],
    #  "reason": str, "allow_ai_fill": bool}
    asset_requirements: dict[str, Any] = Field(default_factory=dict)

    @field_validator("request_id")
    @classmethod
    def _no_blank_id(cls, v: str) -> str:
        import re
        v = v.strip()
        if not v:
            raise ValueError("request_id must not be blank")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", v) or ".." in v or "/" in v:
            raise ValueError("request_id must be a safe slug ([A-Za-z0-9._-], no traversal)")
        return v


class AssetManifest(BaseModel):
    source: str
    license: str
    trust_score: float = Field(ge=0.0, le=1.0)
    rights_status: str
    acquired_at: str = ""


class StrategyOut(BaseModel):
    strategy: str
    reality_ratio: float
    ai_ratio: float
    asset_sources: list[str]
    estimated_runtime: float
    explanation: list[str] = Field(default_factory=list)


# Certification-example compatibility (boundary normalization, NOT a second
# model): maps {origin, script, assets[], content_type short_video,
# output{format,resolution}} onto canonical V2 fields before validation.
_COMPAT_CONTENT_TYPES = {
    "short_video": "video", "video": "video", "anime": "anime",
    "movie": "movie", "film": "movie", "ad": "ad", "ai_film": "ai_film",
}

_COMPAT_RESOLUTIONS = {
    "1080x1920": "1080p", "1920x1080": "1080p", "1280x720": "720p",
    "720x1280": "720p", "3840x2160": "4k",
}


def normalize_compat(payload: dict) -> dict:
    """Translate the external example shape onto canonical V2 (pure)."""
    data = dict(payload or {})
    if "origin" in data and "pulse" not in data:
        data["pulse"] = data.pop("origin")
    if "script" in data and not data.get("narration"):
        data["narration"] = data.pop("script")
    elif "script" in data:
        data.pop("script")
    if "assets" in data and not data.get("sources"):
        data["sources"] = data.pop("assets")
    elif "assets" in data:
        data.pop("assets")
    ct = str(data.get("content_type", "video"))
    data["content_type"] = _COMPAT_CONTENT_TYPES.get(ct, ct)
    output = data.pop("output", None)
    if isinstance(output, dict):
        res = str(output.get("resolution", ""))
        if res and not data.get("resolution"):
            data["resolution"] = _COMPAT_RESOLUTIONS.get(res, "1080p")
    if "language" not in data:
        data["language"] = "en"
    return data
