"""Opportunity Allocation Engine: rank + allocate content resources."""
from __future__ import annotations

from app.core.audit import audit


def score_all(db, actor: str = "allocator") -> list[dict]:
    """Aggregate Trend/Discovery/Profitability/Competitor/Revenue inputs into
    ranked OpportunityScores. Returns the ranked list."""
    from app.models.phase3 import OpportunityScore
    from app.modules.market_intelligence.engine import fastest_growing
    from app.modules.profitability.engine import leaderboard as prof_board
    from app.modules.discovery.engine import weekly_breakout_predictions
    from app.modules.competitors.engine import trend_opportunities
    cands: list[tuple[str, str, float, str]] = []
    for a in fastest_growing(db, "artist", limit=5):
        cands.append((f"artist:{a['key']}", "market", float(a["velocity"]),
                      "fastest-growing artist velocity"))
    for s in fastest_growing(db, "song", limit=5):
        cands.append((f"song:{s['key']}", "market", float(s["velocity"]),
                      "fastest-growing song velocity"))
    for g in prof_board(db, limit=5):
        cands.append((f"genre:{g['genre']}", "genre", float(g["score"]),
                      "profitability score"))
    for b in weekly_breakout_predictions(db, 5):
        cands.append((f"artist:{b['artist']}", "artist",
                      float(b["velocity"]) * 50, "breakout prediction velocity"))
    for o in trend_opportunities(db, 5):
        cands.append((f"content:{o['topic']}", "content",
                      float(o["score"]) * 10, "competitor gap"))
    cands.sort(key=lambda c: c[2], reverse=True)
    out = []
    for key, cat, impact, why in cands[:20]:
        row = OpportunityScore(key=key, category=cat, impact=round(impact, 2),
                               rationale=why)
        db.add(row)
        out.append({"key": key, "category": cat, "impact": round(impact, 2)})
    db.commit()
    audit(db, actor, "allocation.scored", "opportunity", "", {"count": len(out)})
    return out


def priority_queue(db, limit: int = 10) -> list[dict]:
    from app.models.phase3 import OpportunityScore
    rows = (db.query(OpportunityScore)
            .order_by(OpportunityScore.impact.desc()).limit(limit).all())
    return [{"id": r.id, "key": r.key, "category": r.category,
             "impact": r.impact, "allocated": r.allocated} for r in rows]


def allocate(db, top_n: int = 5, actor: str = "allocator") -> dict:
    """Mark top-N opportunities allocated; emit market + genre focus directives."""
    from app.models.phase3 import OpportunityScore
    rows = (db.query(OpportunityScore).filter(OpportunityScore.allocated.is_(False))
            .order_by(OpportunityScore.impact.desc()).limit(top_n).all())
    for r in rows:
        r.allocated = True
    db.commit()
    genres = sorted({r.key.split(":", 1)[1] for r in rows if r.key.startswith("genre:")})
    markets = ["US"]
    try:
        from app.modules.market_intelligence.engine import COUNTRIES
        markets = list(COUNTRIES)
    except Exception:
        pass
    audit(db, actor, "allocation.allocated", "opportunity", "",
          {"count": len(rows), "genres": genres})
    return {"allocated": [r.key for r in rows],
            "market_focus": markets[:3], "genre_focus": genres or ["Pop"]}
