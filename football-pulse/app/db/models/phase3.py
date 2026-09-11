"""Phase 3 decision tables (additive — Phase 1/2 tables untouched).

Design note: the Phase 1 `predictions` table already stores prediction
outputs (probabilities, xG, scoreline, confidence, outcome, correct),
so the Prediction Agent persists there. These new tables track:
- prediction_results: graded outcomes per prediction
- prediction_metrics: rolling accuracy scopes (overall / league:X / team:X)
- content_opportunities: scored content candidates
- executive_decisions: CEO-level decisions + generated task refs
- decision_logs: append-only audit trail of decision events

Phase 1 `tasks` table stores generated content tasks (kind=task_type).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models import _now, _uuid
from app.db.models import TimestampMixin  # noqa: F401


class PredictionResult(Base, TimestampMixin):
    __tablename__ = "prediction_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    prediction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    actual_home_score: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_away_score: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_outcome: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    predicted_outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    scoreline_exact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    brier_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class PredictionMetric(Base, TimestampMixin):
    __tablename__ = "prediction_metrics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    scope: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exact_scorelines: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    brier_avg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ContentOpportunity(Base, TimestampMixin):
    __tablename__ = "content_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    urgency: Mapped[str] = mapped_column(String(16), default="low", nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_platforms: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    estimated_reach: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="proposed", nullable=False, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ExecutiveDecision(Base, TimestampMixin):
    __tablename__ = "executive_decisions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    priority_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    opportunity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    recommendation: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    urgency: Mapped[str] = mapped_column(String(16), default="low", nullable=False)
    expected_reach: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expected_engagement: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tier: Mapped[str] = mapped_column(String(32), default="ignore", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="decided", nullable=False, index=True)
    task_ids: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class DecisionLog(Base, TimestampMixin):
    __tablename__ = "decision_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("executive_decisions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    event: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    logged_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
