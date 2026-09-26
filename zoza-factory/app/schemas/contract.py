"""Factory Contract V2: Pulse sends intent, Zoza decides production strategy.

No publishing fields. No audience-ownership fields. No revenue fields.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


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

    @field_validator("request_id")
    @classmethod
    def _no_blank_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("request_id must not be blank")
        return v.strip()


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
