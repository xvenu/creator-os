"""Phase 6 models: Creator-OS video pipeline (additive — Phases 1-4 untouched)."""
from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContentPackage(Base):
    __tablename__ = "content_packages"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text, default="")
    script: Mapped[str] = mapped_column(Text, default="")
    hashtags_json: Mapped[str] = mapped_column(Text, default="[]")
    keywords_json: Mapped[str] = mapped_column(Text, default="[]")
    thumbnail_brief: Mapped[str] = mapped_column(Text, default="")
    video_brief: Mapped[str] = mapped_column(Text, default="")
    target_market: Mapped[str] = mapped_column(String(8), default="US")
    target_platform: Mapped[str] = mapped_column(String(32), default="youtube")
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_views: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # --- Phase 7 evidence extension (additive; defaults keep old rows valid) ---
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified")
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    rights_status: Mapped[str] = mapped_column(String(32), default="unknown")
    attribution_json: Mapped[str] = mapped_column(Text, default="[]")


class PackageExport(Base):
    __tablename__ = "package_exports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    package_id: Mapped[str] = mapped_column(String(64), index=True)
    channel: Mapped[str] = mapped_column(String(16))  # json|api|queue
    status: Mapped[str] = mapped_column(String(16), default="sent")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ZozaJob(Base):
    __tablename__ = "zoza_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    package_id: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(16), default="created", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)


class RenderResult(Base):
    __tablename__ = "render_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, index=True)
    video_url: Mapped[str] = mapped_column(String(512), default="")
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PublishResult(Base):
    __tablename__ = "publish_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, index=True)
    platform: Mapped[str] = mapped_column(String(32), default="")
    external_id: Mapped[str] = mapped_column(String(128), default="")
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VideoMetric(Base):
    __tablename__ = "video_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, index=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    watch_time_sec: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    retention: Mapped[float] = mapped_column(Float, default=0.0)
    audience_growth: Mapped[int] = mapped_column(Integer, default=0)
    engagement: Mapped[int] = mapped_column(Integer, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EventBusEvent(Base):
    __tablename__ = "event_bus_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    source_pulse: Mapped[str] = mapped_column(String(64), default="music-pulse")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SharedKnowledge(Base):
    __tablename__ = "shared_knowledge"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(32), index=True)  # artist|genre|trend|market|video
    key: Mapped[str] = mapped_column(String(255), index=True)
    value_json: Mapped[str] = mapped_column(Text, default="{}")
    source_pulse: Mapped[str] = mapped_column(String(64), default="music-pulse")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(32))  # views|watch_time|revenue|ctr|retention|growth
    value: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
