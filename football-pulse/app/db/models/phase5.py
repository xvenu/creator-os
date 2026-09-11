"""Phase 5 video-production tables (additive — Phase 1–4 tables untouched).

NOTE: the Phase 1 `videos` table tracks the legacy pipeline stage; Phase 5
uses `video_projects` with a strict lifecycle state machine (see
app.services.video_lifecycle). A nullable `video_id` FK is intentionally
avoided to keep Phase 1 stable — bridging belongs to Phase 6 publishing.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models import _now, _uuid
from app.db.models import TimestampMixin  # noqa: F401


class VideoProject(Base, TimestampMixin):
    __tablename__ = "video_projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    package_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_packages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="16:9", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False, index=True)
    variant_of: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("video_projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    region: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    content_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (Index("ix_video_projects_key", "content_key", unique=True),)


class VideoScene(Base, TimestampMixin):
    __tablename__ = "video_scenes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    narration: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    visual_type: Mapped[str] = mapped_column(String(64), default="generated_image", nullable=False)
    visual_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    on_screen_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transition: Mapped[str] = mapped_column(String(32), default="cut", nullable=False)
    emphasis: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (Index("ix_scenes_project_number", "project_id", "scene_number", unique=True),)


class VoiceAsset(Base, TimestampMixin):
    __tablename__ = "voice_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("video_scenes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    voice_profile: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="unassigned", nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    content_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class VisualAsset(Base, TimestampMixin):
    __tablename__ = "visual_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("video_scenes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    visual_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="unassigned", nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    content_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class SubtitleAsset(Base, TimestampMixin):
    __tablename__ = "subtitle_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    format: Mapped[str] = mapped_column(String(16), default="srt", nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    cue_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RenderJob(Base, TimestampMixin):
    __tablename__ = "render_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    input_manifest: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution: Mapped[str] = mapped_column(String(16), default="1920x1080", nullable=False)
    frame_rate: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    duration: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    codec: Mapped[str] = mapped_column(String(32), default="libx264", nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[str] = mapped_column(String(64), default="ffmpeg", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RenderResult(Base, TimestampMixin):
    __tablename__ = "render_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("render_jobs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    output_path: Mapped[str] = mapped_column(Text, nullable=False)
    duration: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    resolution: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    render_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class QualityReport(Base, TimestampMixin):
    __tablename__ = "quality_reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("render_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    technical_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    audio_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    visual_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    subtitle_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    content_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    brand_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rights_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    findings: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class AssetProvenance(Base, TimestampMixin):
    __tablename__ = "asset_provenance"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    attribution_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attribution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage_status: Mapped[str] = mapped_column(String(32), default="needs_review", nullable=False, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class BrandProfile(Base, TimestampMixin):
    __tablename__ = "brand_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    intro: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    outro: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    logo: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    typography: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    subtitle_style: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    visual_language: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    narration_style: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    pacing: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    transition_style: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    thumbnail_link: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    music_policy: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ProviderRun(Base, TimestampMixin):
    __tablename__ = "provider_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    operation: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="started", nullable=False, index=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_provider_runs_key", "content_key", "provider", "operation"),)
