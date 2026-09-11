"""FootballPulse V2 database models — all 13 required domains.

Covers: news, matches, clubs, players, transfers, predictions,
videos, scripts, analytics, memory, agents, tasks, publications.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class News(Base, TimestampMixin):
    __tablename__ = "news"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    importance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_breaking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (Index("ix_news_breaking_importance", "is_breaking", "importance_score"),)


class Club(Base, TimestampMixin):
    __tablename__ = "clubs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    short_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    league: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    players: Mapped[list["Player"]] = relationship(back_populates="club")
    home_matches: Mapped[list["Match"]] = relationship(back_populates="home_club", foreign_keys="Match.home_club_id")
    away_matches: Mapped[list["Match"]] = relationship(back_populates="away_club", foreign_keys="Match.away_club_id")


class Player(Base, TimestampMixin):
    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    position: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(128), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    club_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    club: Mapped["Club | None"] = relationship(back_populates="players")


class Match(Base, TimestampMixin):
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    home_club_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clubs.id"), nullable=True)
    away_club_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clubs.id"), nullable=True)
    league: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    kickoff_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="scheduled", nullable=False, index=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analysis: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    talking_points: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)

    home_club: Mapped["Club | None"] = relationship(back_populates="home_matches", foreign_keys=[home_club_id])
    away_club: Mapped["Club | None"] = relationship(back_populates="away_matches", foreign_keys=[away_club_id])


class Transfer(Base, TimestampMixin):
    __tablename__ = "transfers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    player_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    player_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    from_club: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_club: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rumor_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credibility_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="rumor", nullable=False, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Prediction(Base, TimestampMixin):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    match_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=True)
    home_win_prob: Mapped[float] = mapped_column(Float, nullable=False, default=0.33)
    draw_prob: Mapped[float] = mapped_column(Float, nullable=False, default=0.34)
    away_win_prob: Mapped[float] = mapped_column(Float, nullable=False, default=0.33)
    expected_home_goals: Mapped[float] = mapped_column(Float, default=1.4, nullable=False)
    expected_away_goals: Mapped[float] = mapped_column(Float, default=1.2, nullable=False)
    predicted_scoreline: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    model_version: Mapped[str] = mapped_column(String(64), default="v0.1", nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Script(Base, TimestampMixin):
    __tablename__ = "scripts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="long_form", nullable=False)  # shorts | long_form
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    fact_check_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    retention_notes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Video(Base, TimestampMixin):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    script_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scripts.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    pipeline_stage: Mapped[str] = mapped_column(String(64), default="research", nullable=False, index=True)
    visual_plan: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    asset_manifest: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    subtitle_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    render_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_check: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Publication(Base, TimestampMixin):
    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    video_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("videos.id", ondelete="SET NULL"), nullable=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    scheduled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Analytics(Base, TimestampMixin):
    __tablename__ = "analytics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    publication_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("publications.id"), nullable=True)
    video_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("videos.id"), nullable=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    retention: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    subscribers_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    raw: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Memory(Base, TimestampMixin):
    __tablename__ = "memory"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    __table_args__ = (Index("ix_memory_kind_key", "kind", "key", unique=True),)


class AgentRecord(Base, TimestampMixin):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_tasks_agent_status", "agent_name", "status"),)


# Phase 2 intelligence tables (additive — see app.db.models.phase2).
from app.db.models.phase2 import (  # noqa: E402, F401
    Campaign,
    CampaignOpportunity,
    MatchAnalysis,
    NewsCluster,
    TransferIntel,
)

# Phase 3 decision tables (additive — see app.db.models.phase3).
# NOTE: predictions are stored in the Phase 1 `predictions` table (reused).
from app.db.models.phase3 import (  # noqa: E402, F401
    ContentOpportunity,
    DecisionLog,
    ExecutiveDecision,
    PredictionMetric,
    PredictionResult,
)

# Phase 4 content tables (additive — see app.db.models.phase4).
# NOTE: scripts are stored in the Phase 1 `scripts` table (reused).
from app.db.models.phase4 import (  # noqa: E402, F401
    ContentPackage,
    ContentPlan,
    PublishingStrategy,
    RegionIntelligence,
    ResearchBrief,
    SEOAsset,
    ThumbnailStrategy,
)

# Phase 5 video-production tables: DEPRECATED (Zoza refactor).
# Historical data preserved — the pulse no longer writes to these tables.
# Video production belongs exclusively to the Zoza Video Factory.
from app.db.models.phase5 import (  # noqa: E402, F401
    AssetProvenance,
    BrandProfile,
    ProviderRun,
    QualityReport,
    RenderJob,
    RenderResult,
    SubtitleAsset,
    VideoProject,
    VideoScene,
    VisualAsset,
    VoiceAsset,
)

# Zoza factory-tracking tables (Creator-OS refactor).
from app.db.models.zoza import (  # noqa: E402, F401
    FactoryStatus,
    ZozaExport,
    ZozaRequest,
)
