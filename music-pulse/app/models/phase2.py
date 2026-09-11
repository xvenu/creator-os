"""Phase 2 normalized models (additive — Phase 1 models untouched)."""
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CountryTrend(Base):
    """Historical per-country trend retention (market intelligence)."""
    __tablename__ = "country_trends"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country: Mapped[str] = mapped_column(String(8), index=True)  # US|CA|UK|AU|DE
    source: Mapped[str] = mapped_column(String(32), default="")
    title: Mapped[str] = mapped_column(String(255))
    artist: Mapped[str] = mapped_column(String(255), default="")
    rank: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    genre: Mapped[str] = mapped_column(String(64), default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class GenreAnalytic(Base):
    """Per-genre per-country analytics (profitability inputs)."""
    __tablename__ = "genre_analytics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    genre: Mapped[str] = mapped_column(String(64), index=True)
    country: Mapped[str] = mapped_column(String(8), default="US", index=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    engagement: Mapped[int] = mapped_column(Integer, default=0)
    posts: Mapped[int] = mapped_column(Integer, default=0)
    retention: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1 audience retention
    sponsorship_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..100
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ArtistDiscovery(Base):
    """Emerging artist tracking."""
    __tablename__ = "artist_discovery"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artist: Mapped[str] = mapped_column(String(255), index=True)
    genre: Mapped[str] = mapped_column(String(64), default="")
    country: Mapped[str] = mapped_column(String(8), default="US")
    followers: Mapped[int] = mapped_column(Integer, default=0)
    streams: Mapped[int] = mapped_column(Integer, default=0)
    velocity: Mapped[float] = mapped_column(Float, default=0.0)  # growth velocity score
    playlist_count: Mapped[int] = mapped_column(Integer, default=0)
    classification: Mapped[str] = mapped_column(String(32), default="Emerging")
    watchlisted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)


class Sponsor(Base):
    __tablename__ = "sponsors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    contact: Mapped[str] = mapped_column(String(255), default="")
    tier: Mapped[str] = mapped_column(String(32), default="standard")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sponsor_id: Mapped[int] = mapped_column(ForeignKey("sponsors.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    package: Mapped[str] = mapped_column(String(64))  # see sponsorships PACKAGES
    country: Mapped[str] = mapped_column(String(8), default="US")
    genre: Mapped[str] = mapped_column(String(64), default="")
    budget: Mapped[float] = mapped_column(Float, default=0.0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="active")
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class RevenueRecord(Base):
    __tablename__ = "revenue_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)  # sponsorship|affiliate|promotion|platform
    sponsor_id: Mapped[int] = mapped_column(Integer, default=0)
    campaign_id: Mapped[int] = mapped_column(Integer, default=0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    country: Mapped[str] = mapped_column(String(8), default="US", index=True)
    genre: Mapped[str] = mapped_column(String(64), default="")
    platform: Mapped[str] = mapped_column(String(32), default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class CompetitorMetric(Base):
    __tablename__ = "competitor_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competitor: Mapped[str] = mapped_column(String(128), index=True)
    platform: Mapped[str] = mapped_column(String(32), default="")
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    formats_json: Mapped[str] = mapped_column(Text, default="{}")
    engagement_est: Mapped[int] = mapped_column(Integer, default=0)
    topics_json: Mapped[str] = mapped_column(Text, default="[]")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
