"""Factory persistence: requests, acquired assets, jobs/timings.

Request states: created → planned → acquiring → assembling → rendering → exported | failed.
"""
from __future__ import annotations

import time

from sqlalchemy import JSON, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProductionRequest(Base):
    __tablename__ = "production_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    pulse: Mapped[str] = mapped_column(String(64), default="")
    goal: Mapped[str] = mapped_column(Text, default="")
    style: Mapped[str] = mapped_column(String(64), default="")
    length_seconds: Mapped[int] = mapped_column(Integer, default=0)
    urgency: Mapped[str] = mapped_column(String(16), default="normal")
    production_mode: Mapped[str] = mapped_column(String(16), default="REALITY_FIRST")
    ai_generation_allowed: Mapped[bool] = mapped_column(default=False)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    voice_profile: Mapped[str] = mapped_column(String(64), default="")
    target_audience: Mapped[str] = mapped_column(String(128), default="")
    priority: Mapped[int] = mapped_column(Integer, default=0)

    state: Mapped[str] = mapped_column(String(16), default="created", index=True)
    strategy_json: Mapped[dict] = mapped_column(JSON, default=dict)
    timeline_json: Mapped[dict] = mapped_column(JSON, default=dict)
    export_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")

    # Capacity tracking (seconds, measured around render/export stages).
    render_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    export_seconds: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)


class ProductionAsset(Base):
    """Catalog row: a real or generated asset the factory can use."""

    __tablename__ = "production_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # real_footage|real_photo|licensed|public_domain|ai_generated
    category: Mapped[str] = mapped_column(String(64), default="")  # official_photo, press, documentary, archive, news, historical...
    source: Mapped[str] = mapped_column(String(256), default="")
    license: Mapped[str] = mapped_column(String(128), default="")
    trust_score: Mapped[float] = mapped_column(Float, default=0.0)
    rights_status: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    acquired_at: Mapped[float] = mapped_column(Float, default=time.time)
