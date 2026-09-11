"""Video Opportunity Engine: score what deserves a Zoza render."""
from __future__ import annotations

from app.core.audit import audit


def score_topic(db, topic: str, market: str = "US") -> dict:
    """Predicted views/watch/engagement/revenue + velocity → one score."""
    from app.modules.market_intelligence.engine import velocity, fastest_growing
    from app.modules.profitability.engine import leaderboard as prof_board
    vel = velocity(db, market.upper(), title=topic)
    fast = {f["key"]: f["velocity"] for f in fastest_growing(db, "song", limit=30)}
    momentum = max(fast.get(topic, 0), abs(vel) * 10)
    prof = (prof_board(db, market.upper(), limit=1) or [{"score": 50}])[0]["score"]
    predicted_views = round(momentum * 100 + prof * 20, 1)
    predicted_watch = round(predicted_views * 0.4, 1)  # ~40% retention assumption
    predicted_eng = round(predicted_views * 0.06, 1)
    predicted_rev = round(predicted_views * 0.002, 2)  # $2 RPM assumption
    score = round(min(momentum + prof, 200), 2)
    return {"topic": topic, "market": market.upper(), "score": score,
            "predicted_views": predicted_views,
            "predicted_watch_time": predicted_watch,
            "predicted_engagement": predicted_eng,
            "predicted_revenue": predicted_rev, "velocity": vel}


def rank_topics(db, topics: list[str], market: str = "US",
                min_score: float = 0.0) -> list[dict]:
    ranked = [score_topic(db, t, market) for t in topics]
    ranked.sort(key=lambda d: d["score"], reverse=True)
    return [r for r in ranked if r["score"] >= min_score]


def top_for_zoza(db, limit: int = 5, market: str = "US") -> list[dict]:
    """Only highest-ranked opportunities leave for Zoza."""
    from app.core.config import get_settings
    from app.modules.market_intelligence.engine import fastest_growing
    songs = [s["key"] for s in fastest_growing(db, "song", limit=limit * 3)]
    return rank_topics(db, songs, market,
                       min_score=get_settings().pipeline_min_priority)[:limit]
