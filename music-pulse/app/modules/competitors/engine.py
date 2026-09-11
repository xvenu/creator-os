"""Competitor Intelligence Engine (Phase 2)."""
from __future__ import annotations
import json
from sqlalchemy import func

from app.core.audit import audit

TRACKED = ("Billboard", "RollingStone", "Pitchfork", "Complex", "XXL",
           "HotNewHipHop", "PopCrave", "IndieWire")


def record_competitor(db, competitor: str, platform: str = "", post_count: int = 0,
                      formats: dict | None = None, engagement_est: int = 0,
                      topics: list | None = None, actor: str = "system"):
    from app.models.phase2 import CompetitorMetric
    row = CompetitorMetric(competitor=competitor, platform=platform,
                           post_count=post_count,
                           formats_json=json.dumps(formats or {}),
                           engagement_est=engagement_est,
                           topics_json=json.dumps(topics or []))
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "competitor.recorded", "competitor", row.id,
          {"competitor": competitor})
    return row


def posting_frequency(db) -> list[dict]:
    from app.models.phase2 import CompetitorMetric
    rows = (db.query(CompetitorMetric.competitor,
                     func.sum(CompetitorMetric.post_count).label("posts"),
                     func.avg(CompetitorMetric.engagement_est).label("eng"))
            .group_by(CompetitorMetric.competitor)
            .order_by(func.sum(CompetitorMetric.post_count).desc()).all())
    return [{"competitor": c, "posts": int(p or 0),
             "avg_engagement": round(float(e or 0), 1)} for c, p, e in rows]


def content_gaps(db, our_topics: list[str] | None = None, limit: int = 10) -> list[dict]:
    """Topics competitors cover that we don't (opportunity list)."""
    from app.models.phase2 import CompetitorMetric
    ours = set(t.lower() for t in (our_topics or []))
    counts: dict[str, int] = {}
    for (blob,) in db.query(CompetitorMetric.topics_json).all():
        try:
            topics = json.loads(blob or "[]")
        except Exception:
            topics = []
        for t in topics:
            if str(t).lower() not in ours:
                counts[str(t)] = counts.get(str(t), 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [{"topic": t, "competitor_mentions": n} for t, n in ranked]


def weakness_report(db) -> list[dict]:
    """Competitors with high volume but low engagement (beatable)."""
    freq = posting_frequency(db)
    weak = [f for f in freq if f["posts"] > 0 and
            (f["avg_engagement"] / max(f["posts"], 1)) < 50]
    weak.sort(key=lambda d: d["avg_engagement"])
    return [{"competitor": w["competitor"], "posts": w["posts"],
             "avg_engagement": w["avg_engagement"],
             "note": "high volume, low engagement — vulnerable"} for w in weak]


def trend_opportunities(db, limit: int = 10) -> list[dict]:
    """Fastest-rising competitor topics not yet saturated."""
    gaps = content_gaps(db, limit=limit)
    return [{"topic": g["topic"], "score": g["competitor_mentions"],
             "action": "cover before saturation"} for g in gaps]
