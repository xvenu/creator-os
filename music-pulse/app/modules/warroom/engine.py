"""Competitive War Room: continuous monitoring, gaps, attack strategies."""
from __future__ import annotations

from app.core.audit import audit


def briefing(db, actor: str = "warroom") -> dict:
    from app.modules.competitors.engine import (
        posting_frequency, content_gaps, weakness_report, trend_opportunities)
    from app.modules.analytics.engine import top_topics
    ours = [t["topic"] for t in top_topics(db, 20)]
    data = {"frequency": posting_frequency(db),
            "gaps": content_gaps(db, our_topics=ours, limit=10),
            "weaknesses": weakness_report(db),
            "opportunities": trend_opportunities(db, 10)}
    audit(db, actor, "warroom.briefed", "warroom", "", {})
    return data


def attack_strategies(db, limit: int = 5) -> list[dict]:
    """Market-takeover recommendations derived from gaps + weaknesses."""
    data = briefing(db)
    strategies = []
    for g in data["gaps"][:limit]:
        strategies.append({
            "target": g["topic"],
            "play": f"Saturate '{g['topic']}' with short-form + rankings before "
                    f"competitors ({g['competitor_mentions']} mentions).",
            "confidence": round(min(g["competitor_mentions"] / 5, 1.0), 2),
        })
    for w in data["weaknesses"][:2]:
        strategies.append({
            "target": w["competitor"],
            "play": f"Out-publish {w['competitor']} on shared topics — "
                    "their engagement per post is weak.",
            "confidence": 0.6,
        })
    return strategies[:limit + 2]
