"""Phase 4 models: growth, prediction, monetization network (additive)."""
from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AudienceMetric(Base):
    __tablename__ = "audience_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(64), index=True)  # social|web|newsletter
    node: Mapped[str] = mapped_column(String(128), default="global")
    followers: Mapped[int] = mapped_column(Integer, default=0)
    subscribers: Mapped[int] = mapped_column(Integer, default=0)
    traffic: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    spend: Mapped[float] = mapped_column(Float, default=0.0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AcquisitionEvent(Base):
    __tablename__ = "acquisition_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64))  # follow|subscribe|visit|convert
    channel: Mapped[str] = mapped_column(String(64), default="")
    node: Mapped[str] = mapped_column(String(128), default="global")
    count: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NetworkNode(Base):
    __tablename__ = "network_nodes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    kind: Mapped[str] = mapped_column(String(32))  # website|brand|account|region|network
    parent: Mapped[str] = mapped_column(String(128), default="")
    region: Mapped[str] = mapped_column(String(8), default="US")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OwnedAsset(Base):
    __tablename__ = "owned_assets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    kind: Mapped[str] = mapped_column(String(32))  # website|domain|newsletter|community|database|product
    traffic: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    growth: Mapped[float] = mapped_column(Float, default=0.0)
    engagement: Mapped[float] = mapped_column(Float, default=0.0)
    valuation: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)


class TrendPrediction(Base):
    __tablename__ = "trend_predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(32))  # artist|song|genre|market
    subject: Mapped[str] = mapped_column(String(255))
    horizon_days: Mapped[int] = mapped_column(Integer, default=7)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    opportunity: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BreakoutAlert(Base):
    __tablename__ = "breakout_alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))  # song|artist|movement|genre_shift
    subject: Mapped[str] = mapped_column(String(255))
    signal: Mapped[float] = mapped_column(Float, default=0.0)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MonetizationRule(Base):
    __tablename__ = "monetization_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    rule_type: Mapped[str] = mapped_column(String(32))  # sponsor_match|pricing|affiliate|inventory
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RevenueAction(Base):
    __tablename__ = "revenue_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(128))
    campaign_id: Mapped[int] = mapped_column(Integer, default=0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="planned")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProductCatalog(Base):
    __tablename__ = "product_catalog"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    kind: Mapped[str] = mapped_column(String(32))  # newsletter|report|intelligence|research
    price: Mapped[float] = mapped_column(Float, default=0.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProductSale(Base):
    __tablename__ = "product_sales"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    retained: Mapped[bool] = mapped_column(Boolean, default=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ForecastResult(Base):
    __tablename__ = "forecast_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(32))  # revenue|growth|market|audience
    horizon: Mapped[str] = mapped_column(String(16))  # weekly|monthly|quarterly|annual
    projection_json: Mapped[str] = mapped_column(Text, default="[]")
    risks_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
