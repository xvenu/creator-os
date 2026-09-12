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


REQUEST_STATES = ("created", "planned", "acquiring", "assembling",
                  "rendering", "exported", "failed")


class ProductionRequestIn(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    pulse: str = ""
    goal: str = Field(min_length=1)
    style: str = ""
    length_seconds: int = Field(gt=0, le=3600)
    urgency: Urgency = Urgency.normal
    production_mode: ProductionMode = ProductionMode.REALITY_FIRST
    ai_generation_allowed: bool = False
    sources: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    voice_profile: str = ""
    target_audience: str = ""
    priority: int = Field(default=0, ge=0, le=100)

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
