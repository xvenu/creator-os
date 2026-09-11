"""SQLAlchemy models for all modules."""
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TrendItem(Mapped if False else Base):
    __tablename__ = "trend_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)  # spotify|youtube|billboard|tiktok
    title: Mapped[str] = mapped_column(String(255))
    artist: Mapped[str] = mapped_column(String(255), default="")
    rank: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    genre: Mapped[str] = mapped_column(String(64), default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ContentItem(Base):
    __tablename__ = "content_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # news|profile|review|ranking|short
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    genre: Mapped[str] = mapped_column(String(64), default="")
    format: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft|queued|published
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PublishJob(Base):
    __tablename__ = "publish_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"))
    platform: Mapped[str] = mapped_column(String(32))  # telegram|x|tiktok|instagram|youtube
    status: Mapped[str] = mapped_column(String(32), default="queued")  # queued|sending|sent|failed
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MetricEvent(Base):
    __tablename__ = "metric_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(Integer, default=0)
    platform: Mapped[str] = mapped_column(String(32), default="")
    views: Mapped[int] = mapped_column(Integer, default=0)
    engagement: Mapped[int] = mapped_column(Integer, default=0)  # likes+comments+shares
    followers_delta: Mapped[int] = mapped_column(Integer, default=0)
    topic: Mapped[str] = mapped_column(String(128), default="")
    genre: Mapped[str] = mapped_column(String(64), default="")
    format: Mapped[str] = mapped_column(String(32), default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128))
    entity_type: Mapped[str] = mapped_column(String(64), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
