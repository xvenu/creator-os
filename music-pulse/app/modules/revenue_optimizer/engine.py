"""Revenue Optimization Agent: maximize MRR, sponsorship, affiliate revenue."""
from __future__ import annotations

from app.core.audit import audit


def optimize(db, actor: str = "optimizer") -> list[dict]:
    """Analyze revenue + profitability + sponsors; persist recommendations."""
    from app.models.phase3 import OptimizationResult
    from app.modules.revenue.engine import summary as rev_summary
    from app.modules.profitability.engine import leaderboard as prof_board
    from app.modules.sponsorships.engine import campaign_performance
    recs: list[tuple[str, str, float]] = []
    rev = rev_summary(db)
    by_source = {r["key"]: r["total"] for r in rev.get("by_source", [])}
    weakest = min(by_source, key=by_source.get) if by_source else "affiliate"
    top_genre = (prof_board(db, limit=1) or [{"genre": "Pop"}])[0]["genre"]
    recs.append(("mrr", f"Push '{top_genre}' inventory (top profitability) to lift MRR "
                        f"toward ${rev['mrr']['target']}.",
                 round(rev["mrr"]["target"] * 0.1, 2)))
    recs.append(("sponsorship", "Renew top-ROI campaigns; package underperforming "
                                "genres with breakout artists.",
                 500.0))
    recs.append(("affiliate", f"'{weakest}' is the weakest revenue stream — "
                              "attach affiliate links to ranking content.",
                 200.0))
    out = []
    for scope, text, uplift in recs:
        row = OptimizationResult(scope=scope, recommendation=text,
                                 expected_uplift=uplift)
        db.add(row)
        out.append({"scope": scope, "recommendation": text,
                    "expected_uplift": uplift})
    db.commit()
    perfs = campaign_performance(db, 3)
    out.append({"scope": "inventory",
                "recommendation": f"Top campaign: {(perfs[0]['name'] if perfs else 'none')} — "
                                  "clone its package for next cycle.",
                "expected_uplift": 300.0})
    audit(db, actor, "revenue.optimized", "optimization", "", {"count": len(out)})
    return out


def results(db, limit: int = 20) -> list[dict]:
    from app.models.phase3 import OptimizationResult
    rows = db.query(OptimizationResult).order_by(
        OptimizationResult.id.desc()).limit(limit).all()
    return [{"id": r.id, "scope": r.scope, "recommendation": r.recommendation,
             "expected_uplift": r.expected_uplift} for r in rows]
