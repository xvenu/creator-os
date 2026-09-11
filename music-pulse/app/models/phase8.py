"""Phase 8 models: refactor mirrors (additive — Phases 1-7 untouched).

Cross-pulse runtime state lives in shared sqlite (notifications.db,
orchestrator.db); these tables mirror what MusicPulse needs for audit/API.
"""
from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExportedAsset(Base):
    """Zoza export received by the Pulse (contract: shared/contracts.py)."""
    __tablename__ = "exported_assets"
    asset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    video: Mapped[str] = mapped_column(String(512), default="")
    thumbnail: Mapped[str] = mapped_column(String(512), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    hashtags_json: Mapped[str] = mapped_column(Text, default="[]")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NotificationMirror(Base):
    __tablename__ = "notification_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event: Mapped[str] = mapped_column(String(32), index=True)
    source_pulse: Mapped[str] = mapped_column(String(64), default="music-pulse")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PulseRegistration(Base):
    __tablename__ = "pulse_registrations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16), default="pulse")  # pulse|factory
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
