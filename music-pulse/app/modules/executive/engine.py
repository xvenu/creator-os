"""Autonomous Executive Agent: highest authority in MusicPulse.

ExecutiveAgent orchestrates memory → strategy → allocation → decision →
director → publish → measure → learn. StrategyPlanner builds daily/weekly/
monthly plans from live data. GoalManager tracks growth/revenue/audience goals.
"""
from __future__ import annotations
import json

from app.core.audit import audit

HORIZONS = ("daily", "weekly", "monthly")


# ---------- GoalManager ----------
def set_goal(db, title: str, category: str = "growth", target: float = 0.0,
             actor: str = "executive"):
    from app.models.phase3 import ExecutiveGoal
    if category not in ("growth", "revenue", "audience"):
        raise ValueError("category must be growth|revenue|audience")
    row = ExecutiveGoal(title=title, category=category, target=target)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "goal.set", "goal", row.id, {"title": title})
    return row


def update_goal_progress(db, goal_id: int, current: float, actor: str = "executive"):
    from app.models.phase3 import ExecutiveGoal
    row = db.get(ExecutiveGoal, goal_id)
    if row is None:
        raise ValueError(f"goal {goal_id} not found")
    row.current = current
    if row.target and current >= row.target:
        row.status = "achieved"
    db.commit()
    audit(db, actor, "goal.updated", "goal", row.id, {"current": current})
    return row


def goals(db, status: str | None = None) -> list[dict]:
    from app.models.phase3 import ExecutiveGoal
    q = db.query(ExecutiveGoal).order_by(ExecutiveGoal.id.desc())
    if status:
        q = q.filter(ExecutiveGoal.status == status)
    return [{"id": r.id, "title": r.title, "category": r.category,
             "target": r.target, "current": r.current, "status": r.status,
             "progress": round(r.current / r.target, 3) if r.target else 0.0}
            for r in q.all()]


# ---------- StrategyPlanner ----------
def generate_strategy(db, horizon: str = "daily", actor: str = "executive") -> dict:
    """Auto-generate a strategic plan from live business data."""
    from app.models.phase3 import StrategicPlan
    from app.modules.memory.engine import lessons
    from app.modules.market_intelligence.engine import fastest_growing, COUNTRIES
    from app.modules.profitability.engine import leaderboard as prof_board
    from app.modules.discovery.engine import weekly_breakout_predictions
    from app.modules.revenue.engine import mrr
    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be {HORIZONS}")
    mem = lessons(db, 3)
    top_genres = [g["genre"] for g in prof_board(db, limit=3)]
    breakouts = [b["artist"] for b in weekly_breakout_predictions(db, 3)]
    fast_songs = [s["key"] for s in fastest_growing(db, "song", limit=3)]
    volume = {"daily": 5, "weekly": 25, "monthly": 100}[horizon]
    m = mrr(db)
    plan = {
        "horizon": horizon,
        "markets": list(COUNTRIES[:3]),
        "genres": top_genres or ["Pop"],
        "artists": (breakouts + fast_songs)[:5],
        "posting_volume": volume,
        "revenue_target": round(m["target"] * {"daily": 1 / 30, "weekly": 7 / 30, "monthly": 1}[horizon], 2),
        "growth_target": round(volume * 200.0, 1),  # target new views
        "rationale": (f"Auto-strategy from live profitability, breakout and velocity "
                      f"signals; consulted {len(mem)} memory lessons."),
    }
    row = StrategicPlan(horizon=horizon, markets_json=json.dumps(plan["markets"]),
                        genres_json=json.dumps(plan["genres"]),
                        artists_json=json.dumps(plan["artists"]),
                        posting_volume=volume, revenue_target=plan["revenue_target"],
                        growth_target=plan["growth_target"], rationale=plan["rationale"])
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "strategy.generated", "plan", row.id, {"horizon": horizon})
    return {"id": row.id, **plan}


def latest_strategy(db, horizon: str = "daily") -> dict | None:
    from app.models.phase3 import StrategicPlan
    r = (db.query(StrategicPlan).filter(StrategicPlan.horizon == horizon)
         .order_by(StrategicPlan.id.desc()).first())
    if not r:
        return None
    return {"id": r.id, "horizon": r.horizon,
            "markets": json.loads(r.markets_json or "[]"),
            "genres": json.loads(r.genres_json or "[]"),
            "artists": json.loads(r.artists_json or "[]"),
            "posting_volume": r.posting_volume, "revenue_target": r.revenue_target,
            "growth_target": r.growth_target, "rationale": r.rationale}


# ---------- ExecutiveAgent ----------
class ExecutiveAgent:
    """Highest authority: analyze → plan → prioritize → allocate → decide."""

    #: Reality-first priority. Never reverse this order.
    DECISION_PRIORITY = ("verified_reality", "strong_evidence", "historical_knowledge",
                         "predictive_models", "ai_inference")

    @staticmethod
    def decide_reality_first(db, question: str, actor: str = "executive") -> dict:
        """Answer a strategic question grounding each tier in order; tiers
        without support abstain instead of falling through to AI inference."""
        from app.modules.verification.engine import verification_status
        from app.modules.memory.engine import lessons
        from app.modules.prediction.engine import forecast_report
        verdict = verification_status(db, question)
        used, tiers = [], {}
        if verdict == "verified":
            tiers["verified_reality"] = f"claim verified: {question}"
            used.append("verified_reality")
        from app.models.phase7 import EvidenceRecord
        nev = db.query(EvidenceRecord).filter(
            EvidenceRecord.claim.like(f"%{question[:40]}%")).count()
        if nev >= 2:
            tiers["strong_evidence"] = f"{nev} evidence items support action"
            used.append("strong_evidence")
        mem = lessons(db, 3)
        if mem:
            tiers["historical_knowledge"] = f"{len(mem)} lessons consulted"
            used.append("historical_knowledge")
        fc = forecast_report(db, 30, 3)
        if fc:
            tiers["predictive_models"] = f"{len(fc)} forecasts weigh in"
            used.append("predictive_models")
        # ai_inference is last resort and must be labeled as such
        decision = (f"Proceed on {used[0]}" if used
                    else "Abstain: no tier above AI inference has support")
        if not used:
            used.append("ai_inference")
        audit(db, actor, "decision.reality_first", "decision", "",
              {"question": question, "tier": used[0]})
        return {"question": question, "tier": used[0], "decision": decision,
                "tiers": tiers, "priority": list(ExecutiveAgent.DECISION_PRIORITY)}

    @staticmethod
    def analyze(db) -> dict:
        from app.modules.analytics.engine import totals
        from app.modules.revenue.engine import summary as rev_summary
        from app.modules.profitability.engine import leaderboard as prof_board
        from app.modules.allocation.engine import priority_queue
        return {"analytics": totals(db), "revenue": rev_summary(db),
                "top_genres": prof_board(db, limit=3),
                "opportunities": priority_queue(db, 5)}

    @classmethod
    def run(cls, db, horizon: str = "daily", actor: str = "executive") -> dict:
        """One executive pass: strategy + allocation + focus decisions."""
        from app.modules.allocation.engine import score_all, allocate
        from app.modules.decision.engine import decide_focus
        from app.modules.memory.engine import store
        snapshot = cls.analyze(db)
        strategy = generate_strategy(db, horizon, actor)
        scored = score_all(db, actor)
        alloc = allocate(db, actor=actor)
        focus = decide_focus(db, actor)
        store(db, "decision", f"Executive run ({horizon})",
              json.dumps({"strategy": strategy["id"], "allocated": alloc["allocated"]}),
              actor=actor)
        return {"snapshot": snapshot, "strategy": strategy,
                "scored": len(scored), "allocation": alloc, "focus": focus}
