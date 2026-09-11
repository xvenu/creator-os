"""Phase 4 content tables (additive — Phase 1/2/3 tables untouched).

Design note: the Phase 1 `scripts` table already stores script outputs
(title/kind/body/status/fact_check_status), so the Script Writer Agent
persists there. New tables cover the rest of the content pipeline:
- research_briefs: aggregated facts/entities/timelines per topic
- content_plans: calendar entries (what/when/platforms/priority)
- seo_assets: titles/descriptions/tags/hashtags per script
- thumbnail_strategies: click concepts (no image bytes yet — Phase 5)
- region_intelligence: monetization snapshots per region
- content_packages: assembled publish-ready bundles (FKs to each asset)
- publishing_strategies: per-package rollout plans
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models import _now, _uuid
from app.db.models import TimestampMixin  # noqa: F401


class ResearchBrief(Base, TimestampMixin):
    __tablename__ = "research_briefs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    facts: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    entities: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    timeline: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    supporting_points: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    references: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ContentPlan(Base, TimestampMixin):
    __tablename__ = "content_plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    content_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    publish_priority: Mapped[str] = mapped_column(String(16), default="medium", nullable=False, index=True)
    publish_window: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    platform_targets: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    expected_reach: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="scheduled", nullable=False, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class SEOAsset(Base, TimestampMixin):
    __tablename__ = "seo_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    script_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scripts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title_options: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    keywords: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    hashtags: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    seo_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ThumbnailStrategy(Base, TimestampMixin):
    __tablename__ = "thumbnail_strategies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    script_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scripts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    thumbnail_text: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    visual_elements: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    emotional_trigger: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    color_strategy: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    click_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RegionIntelligence(Base, TimestampMixin):
    __tablename__ = "region_intelligence"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    region: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tier: Mapped[int] = mapped_column(Integer, default=3, nullable=False, index=True)
    cpm_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rpm_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    football_interest: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    competition_popularity: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    language_performance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    recommended_language: Mapped[str] = mapped_column(String(32), default="en", nullable=False)
    recommended_publish_time: Mapped[str] = mapped_column(String(32), default="18:00 UTC", nullable=False)
    monetization_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    audience_quality: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (Index("ix_region_monetization", "monetization_score"),)


class ContentPackage(Base, TimestampMixin):
    __tablename__ = "content_packages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    brief_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("research_briefs.id"), nullable=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_plans.id"), nullable=True)
    script_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scripts.id"), nullable=True)
    seo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seo_assets.id"), nullable=True)
    thumbnail_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("thumbnail_strategies.id"), nullable=True)
    target_regions: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    quality: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="assembled", nullable=False, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class PublishingStrategy(Base, TimestampMixin):
    __tablename__ = "publishing_strategies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    package_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_packages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    best_regions: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    best_language: Mapped[str] = mapped_column(String(32), default="en", nullable=False)
    best_publish_time: Mapped[str] = mapped_column(String(32), default="18:00 UTC", nullable=False)
    platform_schedule: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    revenue_opportunity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
