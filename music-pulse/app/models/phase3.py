"""Phase 3 models: autonomous company (additive — Phases 1-2 untouched)."""
from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExecutiveGoal(Base):
    __tablename__ = "executive_goals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(32), default="growth")  # growth|revenue|audience
    target: Mapped[float] = mapped_column(Float, default=0.0)
    current: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StrategicPlan(Base):
    __tablename__ = "strategic_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    horizon: Mapped[str] = mapped_column(String(16), index=True)  # daily|weekly|monthly
    markets_json: Mapped[str] = mapped_column(Text, default="[]")
    genres_json: Mapped[str] = mapped_column(Text, default="[]")
    artists_json: Mapped[str] = mapped_column(Text, default="[]")
    posting_volume: Mapped[int] = mapped_column(Integer, default=0)
    revenue_target: Mapped[float] = mapped_column(Float, default=0.0)
    growth_target: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BusinessMemory(Base):
    __tablename__ = "business_memory"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # decision|outcome|success|failure|lesson|market
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)  # outcome score for lessons
    ref_type: Mapped[str] = mapped_column(String(64), default="")
    ref_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OpportunityScore(Base):
    __tablename__ = "opportunity_scores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(255), index=True)  # e.g. genre:Pop:US
    category: Mapped[str] = mapped_column(String(32))  # market|genre|artist|content
    impact: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, default="")
    allocated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExecutiveDecision(Base):
    __tablename__ = "executive_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(String(512))
    options_json: Mapped[str] = mapped_column(Text, default="[]")
    chosen: Mapped[str] = mapped_column(String(255))
    rationale: Mapped[str] = mapped_column(Text, default="")
    memory_refs_json: Mapped[str] = mapped_column(Text, default="[]")
    outcome: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PolicyEvent(Base):
    __tablename__ = "policy_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule: Mapped[str] = mapped_column(String(64), index=True)
    verdict: Mapped[str] = mapped_column(String(16))  # pass|block
    content_ref: Mapped[str] = mapped_column(String(128), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AutonomyCycle(Base):
    __tablename__ = "autonomy_cycles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")  # completed|failed|stopped
    stages_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OptimizationResult(Base):
    __tablename__ = "optimization_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(32))  # mrr|sponsorship|affiliate|inventory
    recommendation: Mapped[str] = mapped_column(Text, default="")
    expected_uplift: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
