"""Phase 2 intelligence tables.

Additive to Phase 1 models — existing tables are NOT modified.

New tables:
- news_clusters: story clusters over news items
- match_analysis: structured tactical/performance analyses per match
- transfer_intelligence: rumor/confirmed tracking with credibility + probability
- campaigns: clipping campaign directory
- campaign_opportunities: scored campaign recommendations
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models import _now, _uuid
from app.db.models import TimestampMixin  # noqa: F401  (re-export for alembic autogenerate clarity)


class NewsCluster(Base, TimestampMixin):
    __tablename__ = "news_clusters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    story_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    article_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trend_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    importance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_breaking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    article_ids: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    entities: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (Index("ix_news_clusters_trend", "trend_score"),)


class MatchAnalysis(Base, TimestampMixin):
    __tablename__ = "match_analysis"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=True, index=True
    )
    home_club: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    away_club: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    league: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="upcoming", nullable=False, index=True)
    key_events: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    tactical_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    standout_players: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    strengths: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    weaknesses: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    momentum: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    form: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    narrative: Mapped[str] = mapped_column(Text, default="", nullable=False)
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class TransferIntel(Base, TimestampMixin):
    __tablename__ = "transfer_intelligence"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    player: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    from_club: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_club: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="rumor", nullable=False, index=True)
    credibility_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sources: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    timeline: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    last_updated: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_transfer_intel_player_status", "player", "status"),
        Index("ix_transfer_intel_probability", "probability"),
    )


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    campaign_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payout_model: Mapped[str] = mapped_column(String(64), nullable=False)
    payout_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    requirements: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    niche: Mapped[str] = mapped_column(String(64), default="football", nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    countries: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CampaignOpportunity(Base, TimestampMixin):
    __tablename__ = "campaign_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True, index=True
    )
    campaign_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    roi_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    payout_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
