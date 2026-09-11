"""Analytics Engine: views, engagement, follower growth, top topics."""
from __future__ import annotations
from sqlalchemy import func

from app.core.audit import audit


def record_metric(db, content_id: int = 0, platform: str = "", views: int = 0,
                  engagement: int = 0, followers_delta: int = 0,
                  topic: str = "", genre: str = "", format: str = ""):
    from app.models.models import MetricEvent
    row = MetricEvent(content_id=content_id, platform=platform, views=views,
                      engagement=engagement, followers_delta=followers_delta,
                      topic=topic, genre=genre, format=format)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, "analytics", "metric.recorded", "metric", row.id, {"topic": topic})
    return row


def totals(db) -> dict:
    from app.models.models import MetricEvent
    v, e, f = db.query(
        func.coalesce(func.sum(MetricEvent.views), 0),
        func.coalesce(func.sum(MetricEvent.engagement), 0),
        func.coalesce(func.sum(MetricEvent.followers_delta), 0),
    ).one()
    return {"views": int(v), "engagement": int(e), "followers_delta": int(f)}


def top_topics(db, limit: int = 10) -> list[dict]:
    from app.models.models import MetricEvent
    rows = (db.query(MetricEvent.topic,
                     func.sum(MetricEvent.views).label("views"),
                     func.sum(MetricEvent.engagement).label("engagement"))
            .group_by(MetricEvent.topic)
            .order_by(func.sum(MetricEvent.views).desc())
            .limit(limit).all())
    return [{"topic": t or "(untagged)", "views": int(v or 0), "engagement": int(e or 0)}
            for t, v, e in rows]


def engagement_rate(db) -> float:
    t = totals(db)
    if not t["views"]:
        return 0.0
    return round(t["engagement"] / t["views"], 4)
