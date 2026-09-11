"""Zoza factory-tracking tables (Creator-OS refactor).

Replaces local video-asset writes. Deprecated Phase 5 tables
(render_jobs, render_results, voice_assets, subtitle_assets,
visual_assets, plus video_projects/scenes, quality_reports,
asset_provenance, brand_profiles, provider_runs) are preserved
untouched for historical data — nothing is dropped or migrated.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models import _now, _uuid
from app.db.models import TimestampMixin  # noqa: F401


class ZozaRequest(Base, TimestampMixin):
    """Pulse-side record of one package submission to the factory."""

    __tablename__ = "zoza_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    package_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_packages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    zoza_job_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    state: Mapped[str] = mapped_column(String(32), default="created", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ZozaExport(Base, TimestampMixin):
    """Contract-validated factory output, ready for Pulse publishing."""

    __tablename__ = "zoza_exports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("zoza_requests.id", ondelete="SET NULL"), nullable=True, index=True
    )
    zoza_job_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    video_path: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_path: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    hashtags: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="exported", nullable=False, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class FactoryStatus(Base, TimestampMixin):
    """Reachability snapshot of the Zoza factory (one row per component)."""

    __tablename__ = "factory_status"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    component: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    reachable: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_checked: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
