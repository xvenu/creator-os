"""Audience Acquisition Engine: growth tracking, funnels, forecasts."""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import func

from app.core.audit import audit


class AudienceAcquisitionEngine:
    @staticmethod
    def record_snapshot(db, channel: str, node: str = "global", followers: int = 0,
                        subscribers: int = 0, traffic: int = 0, conversions: int = 0,
                        spend: float = 0.0, actor: str = "acquisition"):
        from app.models.phase4 import AudienceMetric
        row = AudienceMetric(channel=channel, node=node, followers=followers,
                             subscribers=subscribers, traffic=traffic,
                             conversions=conversions, spend=spend)
        db.add(row)
        db.commit()
        db.refresh(row)
        audit(db, actor, "acquisition.snapshot", "audience", row.id,
              {"channel": channel, "node": node})
        return row

    @staticmethod
    def record_event(db, event_type: str, channel: str = "", node: str = "global",
                     count: int = 0, cost: float = 0.0, actor: str = "acquisition"):
        from app.models.phase4 import AcquisitionEvent
        if event_type not in ("follow", "subscribe", "visit", "convert"):
            raise ValueError("event_type must be follow|subscribe|visit|convert")
        row = AcquisitionEvent(event_type=event_type, channel=channel, node=node,
                               count=count, cost=cost)
        db.add(row)
        db.commit()
        db.refresh(row)
        audit(db, actor, "acquisition.event", "acquisition", row.id,
              {"type": event_type, "count": count})
        return row


class FollowerGrowthTracker:
    @staticmethod
    def per_day(db, node: str = "global", days: int = 7) -> float:
        from app.models.phase4 import AudienceMetric
        now = datetime.utcnow()
        lo = db.query(func.coalesce(func.max(AudienceMetric.followers), 0)).filter(
            AudienceMetric.node == node,
            AudienceMetric.recorded_at < now - timedelta(days=days)).scalar() or 0
        hi = db.query(func.coalesce(func.max(AudienceMetric.followers), 0)).filter(
            AudienceMetric.node == node).scalar() or 0
        return round((float(hi) - float(lo)) / max(days, 1), 2)


class SubscriberGrowthTracker:
    @staticmethod
    def per_day(db, node: str = "global", days: int = 7) -> float:
        from app.models.phase4 import AudienceMetric
        now = datetime.utcnow()
        lo = db.query(func.coalesce(func.max(AudienceMetric.subscribers), 0)).filter(
            AudienceMetric.node == node,
            AudienceMetric.recorded_at < now - timedelta(days=days)).scalar() or 0
        hi = db.query(func.coalesce(func.max(AudienceMetric.subscribers), 0)).filter(
            AudienceMetric.node == node).scalar() or 0
        return round((float(hi) - float(lo)) / max(days, 1), 2)


class TrafficGrowthTracker:
    @staticmethod
    def rate(db, node: str = "global", days: int = 7) -> float:
        from app.models.phase4 import AudienceMetric
        now = datetime.utcnow()
        old = db.query(func.coalesce(func.sum(AudienceMetric.traffic), 0)).filter(
            AudienceMetric.node == node,
            AudienceMetric.recorded_at < now - timedelta(days=days)).scalar() or 0
        new = db.query(func.coalesce(func.sum(AudienceMetric.traffic), 0)).filter(
            AudienceMetric.node == node,
            AudienceMetric.recorded_at >= now - timedelta(days=days)).scalar() or 0
        if not old:
            return round(1.0 if new else 0.0, 4)
        return round((float(new) - float(old)) / float(old), 4)


class ConversionAnalyzer:
    @staticmethod
    def funnel(db, node: str = "global") -> dict:
        from app.models.phase4 import AcquisitionEvent
        rows = (db.query(AcquisitionEvent.event_type,
                         func.sum(AcquisitionEvent.count).label("n"),
                         func.sum(AcquisitionEvent.cost).label("c"))
                .filter(AcquisitionEvent.node == node)
                .group_by(AcquisitionEvent.event_type).all())
        by_type = {t: (int(n or 0), float(c or 0)) for t, n, c in rows}
        visits = by_type.get("visit", (0, 0))[0]
        converts = by_type.get("convert", (0, 0))[0]
        total_cost = sum(c for _, c in by_type.values())
        rate = (converts / visits) if visits else 0.0
        cpa = (total_cost / converts) if converts else 0.0
        ltv = round(converts * 2.5, 2)  # heuristic $2.50 lifetime value per conversion
        return {"visits": visits, "conversions": converts,
                "conversion_rate": round(rate, 4), "cpa": round(cpa, 2),
                "ltv": ltv, "by_type": {k: v[0] for k, v in by_type.items()}}


def growth_report(db, node: str = "global") -> dict:
    return {"node": node,
            "followers_per_day": FollowerGrowthTracker.per_day(db, node),
            "subscribers_per_day": SubscriberGrowthTracker.per_day(db, node),
            "traffic_growth_rate": TrafficGrowthTracker.rate(db, node),
            "funnel": ConversionAnalyzer.funnel(db, node)}


def acquisition_recommendations(db, node: str = "global") -> list[dict]:
    from app.core.config import get_settings
    rep = growth_report(db, node)
    s = get_settings()
    recs = []
    if rep["followers_per_day"] < s.growth_target_followers_per_day:
        recs.append({"area": "social",
                     "action": "increase short-form volume on top-velocity topics",
                     "reason": "followers/day below target"})
    if rep["funnel"]["conversion_rate"] < 0.02:
        recs.append({"area": "funnel",
                     "action": "add newsletter CTA to ranking content",
                     "reason": "conversion rate below 2%"})
    if rep["funnel"]["cpa"] > s.default_cpa_cap and rep["funnel"]["conversions"]:
        recs.append({"area": "spend",
                     "action": "shift budget to organic breakout coverage",
                     "reason": "CPA above cap"})
    return recs or [{"area": "all", "action": "maintain current mix",
                     "reason": "all metrics within targets"}]


def audience_forecast(db, node: str = "global", days: int = 30) -> dict:
    fpd = FollowerGrowthTracker.per_day(db, node)
    spd = SubscriberGrowthTracker.per_day(db, node)
    return {"node": node, "days": days,
            "projected_followers": round(fpd * days, 1),
            "projected_subscribers": round(spd * days, 1)}
