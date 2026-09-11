"""Learning Engine: which genres/formats perform best + recommendations."""
from __future__ import annotations
from sqlalchemy import func


def _score_by(db, column: str, limit: int = 10) -> list[dict]:
    from app.models.models import MetricEvent
    col = {"genre": MetricEvent.genre, "format": MetricEvent.format,
           "topic": MetricEvent.topic}[column]
    rows = (db.query(col, func.sum(MetricEvent.views).label("views"),
                     func.sum(MetricEvent.engagement).label("eng"))
            .group_by(col).all())
    scored = []
    for key, views, eng in rows:
        views, eng = int(views or 0), int(eng or 0)
        rate = (eng / views) if views else 0.0
        scored.append({"key": key or "unknown", "views": views,
                       "engagement": eng, "rate": round(rate, 4),
                       "score": round(views * (1 + rate), 2)})
    scored.sort(key=lambda d: d["score"], reverse=True)
    return scored[:limit]


def best_genres(db, limit: int = 5) -> list[dict]:
    return _score_by(db, "genre", limit)


def best_formats(db, limit: int = 5) -> list[dict]:
    return _score_by(db, "format", limit)


def recommend(db, n: int = 5) -> list[dict]:
    """Recommend future content: cartesian best-genre x best-format with topic hint."""
    from app.modules.analytics.engine import top_topics
    genres = best_genres(db, 3)
    formats = best_formats(db, 3)
    topics = top_topics(db, 3)
    recs: list[dict] = []
    for g in genres or [{"key": "pop"}]:
        for f in formats or [{"key": "short"}]:
            hint = topics[0]["topic"] if topics else "viral hit"
            recs.append({
                "genre": g["key"], "format": f["key"],
                "suggested_kind": "short" if f["key"] in ("caption", "short") else "news",
                "suggested_topic": hint,
                "reason": f"genre '{g['key']}' x format '{f['key']}' scored highest",
            })
            if len(recs) >= n:
                return recs
    return recs
