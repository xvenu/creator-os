"""Phase 4 Pydantic schemas — research → package pipeline I/O."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class BriefJobIn(BaseModel):
    topic: str
    items: list[dict] = Field(default_factory=list)


class ScriptJobIn(BaseModel):
    brief: dict | None = None
    topic: str | None = None
    facts: list[dict] = Field(default_factory=list)
    supporting_points: list[str] = Field(default_factory=list)
    entities: dict = Field(default_factory=dict)
    content_format: str = "football_story"
    length: str = "60s"


class SEOJobIn(BaseModel):
    topic: str | None = None
    title: str | None = None
    summary: str = ""
    body: str = ""
    script_id: uuid.UUID | None = None


class ThumbnailJobIn(BaseModel):
    topic: str
    content_format: str = "football_story"
    entities: dict = Field(default_factory=dict)
    urgency: str = "medium"
    script_id: uuid.UUID | None = None


class PackageJobIn(BaseModel):
    topic: str
    content_type: str = "short"
    script: dict = Field(default_factory=dict)
    seo: dict = Field(default_factory=dict)
    thumbnail: dict = Field(default_factory=dict)
    regions: list = Field(default_factory=list)
    quality: dict = Field(default_factory=dict)
    opportunity_score: float = 0.0
    platform_targets: list[str] = Field(default_factory=lambda: ["youtube", "tiktok"])
    brief_id: uuid.UUID | None = None
    plan_id: uuid.UUID | None = None
    script_id: uuid.UUID | None = None
    seo_id: uuid.UUID | None = None
    thumbnail_id: uuid.UUID | None = None
