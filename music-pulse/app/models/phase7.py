"""Phase 7 models: reality-first intelligence (additive — Phases 1-6 untouched)."""
from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(512), default="")
    kind: Mapped[str] = mapped_column(String(32), index=True)  # artist|label|press|news|industry|event
    official: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SourceScore(Base):
    __tablename__ = "source_scores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, index=True)
    trust: Mapped[float] = mapped_column(Float, default=0.0)
    freshness: Mapped[float] = mapped_column(Float, default=0.0)
    authority: Mapped[float] = mapped_column(Float, default=0.0)
    reliability: Mapped[float] = mapped_column(Float, default=0.0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim: Mapped[str] = mapped_column(String(512))
    source_id: Mapped[int] = mapped_column(Integer, default=0)
    url: Mapped[str] = mapped_column(String(512), default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32))  # presskit|photo|promo|artwork|bio|event_image
    ref_url: Mapped[str] = mapped_column(String(512), default="")  # reference only, never copied
    rights_status: Mapped[str] = mapped_column(String(32), default="unknown")
    attribution: Mapped[str] = mapped_column(String(255), default="")
    source_id: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VerificationEvent(Base):
    __tablename__ = "verification_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(512))
    category: Mapped[str] = mapped_column(String(32))  # artist|release|concert|claim|story
    verdict: Mapped[str] = mapped_column(String(32), index=True)  # verified|unverified|disputed|insufficient
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ArtistProfile(Base):
    __tablename__ = "artist_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artist: Mapped[str] = mapped_column(String(255), unique=True)
    label: Mapped[str] = mapped_column(String(255), default="")
    genre: Mapped[str] = mapped_column(String(64), default="")
    bio_ref: Mapped[str] = mapped_column(String(512), default="")
    momentum: Mapped[float] = mapped_column(Float, default=0.0)
    coverage: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)


class LabelProfile(Base):
    __tablename__ = "label_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(255), unique=True)
    kind: Mapped[str] = mapped_column(String(32), default="independent")  # major|independent|emerging
    signings: Mapped[int] = mapped_column(Integer, default=0)
    releases: Mapped[int] = mapped_column(Integer, default=0)
    activity: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)


class NewsroomReport(Base):
    __tablename__ = "newsroom_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))  # news|analysis|market|release|event
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, default="")
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    verification: Mapped[str] = mapped_column(String(32), default="unverified")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentaryProject(Base):
    __tablename__ = "documentary_projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(255))
    brief: Mapped[str] = mapped_column(Text, default="")
    script: Mapped[str] = mapped_column(Text, default="")
    research_json: Mapped[str] = mapped_column(Text, default="{}")
    package_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RightsRecord(Base):
    __tablename__ = "rights_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(Integer, index=True)
    restriction: Mapped[str] = mapped_column(String(255), default="")
    license: Mapped[str] = mapped_column(String(128), default="unknown")
    owner: Mapped[str] = mapped_column(String(255), default="")
    attribution_required: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
