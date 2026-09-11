"""Multi-format content system: auto-decide optimal video format."""
from __future__ import annotations

FORMATS = ("shorts", "reels", "tiktok", "longform", "documentary", "news",
           "listicle", "deepdive", "biography")

# heuristic weights per signal source
_FORMAT_SIGNALS = {
    "shorts": {"velocity": 3.0, "breakout": 2.0},
    "reels": {"velocity": 2.5, "breakout": 1.5},
    "tiktok": {"velocity": 3.0, "viral": 2.0},
    "longform": {"established": 2.0, "documentary_demand": 1.5},
    "documentary": {"established": 2.5},
    "news": {"fresh": 2.0, "velocity": 1.0},
    "listicle": {"ranking": 2.0, "fresh": 1.0},
    "deepdive": {"established": 1.5, "engagement": 1.5},
    "biography": {"artist_heat": 2.0},
}


def recommend_format(db, topic: str, market: str = "US") -> dict:
    """Score formats from live velocity/breakout/discovery signals."""
    from app.modules.video_opportunities.engine import score_topic
    from app.modules.breakout.engine import watchlist
    scored = score_topic(db, topic, market)
    hot = {w["subject"].lower() for w in watchlist(db, limit=20)}
    signals = {"velocity": min(scored["score"] / 50, 3.0),
               "breakout": 2.0 if topic.lower() in hot else 0.0,
               "viral": 2.0 if scored["score"] > 120 else 0.0,
               "established": 1.0 if scored["score"] < 40 else 0.0,
               "fresh": 2.0, "ranking": 1.0, "engagement": 1.0,
               "artist_heat": 1.5 if topic.lower() in hot else 0.5,
               "documentary_demand": 0.5}
    ranked = sorted(
        ((f, round(sum(w * signals.get(k, 0) for k, w in weights.items()), 2))
         for f, weights in _FORMAT_SIGNALS.items()),
        key=lambda kv: kv[1], reverse=True)
    return {"topic": topic, "format": ranked[0][0], "score": ranked[0][1],
            "ranking": [{"format": f, "score": s} for f, s in ranked],
            "rationale": f"velocity={scored['velocity']}, breakout={topic.lower() in hot}"}


def performance_report(db) -> list[dict]:
    """Format performance from measured video metrics."""
    from app.modules.video_intelligence.engine import best_formats
    return best_formats(db, limit=9)
