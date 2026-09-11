"""Decision Engine: explainable, auditable optimal-action selection."""
from __future__ import annotations
import json

from app.core.audit import audit


def evaluate(db, question: str, options: list[dict], actor: str = "executive") -> dict:
    """options: [{name, signals: {metric: value}, weights?: {metric: w}}].
    Consults memory lessons, scores options, persists ExecutiveDecision."""
    from app.models.phase3 import ExecutiveDecision
    from app.modules.memory.engine import lessons
    mem = lessons(db, 5)
    mem_titles = [m["title"] for m in mem]
    scored = []
    for opt in options:
        signals = opt.get("signals", {})
        weights = opt.get("weights", {})
        total = sum(float(signals.get(k, 0.0)) * float(weights.get(k, 1.0))
                    for k in signals)
        # memory nudge: +5% if option name appears in past successes
        if any(opt.get("name", "").lower() in t.lower() for t in mem_titles):
            total *= 1.05
        scored.append({"name": opt.get("name", "?"), "score": round(total, 3)})
    scored.sort(key=lambda d: d["score"], reverse=True)
    chosen = scored[0]["name"] if scored else "none"
    rationale = (f"Chose '{chosen}' from {len(options)} options by weighted signals; "
                 f"consulted {len(mem)} memory lessons.")
    row = ExecutiveDecision(question=question, options_json=json.dumps(scored),
                            chosen=chosen, rationale=rationale,
                            memory_refs_json=json.dumps(mem_titles))
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "decision.made", "decision", row.id,
          {"question": question, "chosen": chosen})
    return {"id": row.id, "chosen": chosen, "scores": scored, "rationale": rationale}


def decide_focus(db, actor: str = "executive") -> dict:
    """Canonical company questions answered from live engines."""
    from app.modules.profitability.engine import leaderboard as prof_board
    from app.modules.market_intelligence.engine import fastest_growing
    genres = {g["genre"]: g["score"] for g in prof_board(db, limit=10)}
    g_opts = [{"name": k, "signals": {"profit": v}} for k, v in genres.items()]
    genre_dec = evaluate(db, "Should MusicPulse focus on Hip-Hop or Pop?",
                         [o for o in g_opts if o["name"] in ("Hip-Hop", "Pop")] or g_opts[:2],
                         actor)
    mk = fastest_growing(db, "artist", limit=10)
    mkt_scores: dict[str, float] = {}
    for m in mk:
        mkt_scores["US"] = mkt_scores.get("US", 0) + 0  # artist-level has no country; use markets below
    from app.modules.market_intelligence.engine import COUNTRIES, country_rankings
    for c in COUNTRIES:
        ranks = country_rankings(db, c, 5)
        mkt_scores[c] = sum(r["score"] for r in ranks)
    market_dec = evaluate(db, "Which market should MusicPulse prioritize?",
                          [{"name": k, "signals": {"heat": v}} for k, v in mkt_scores.items()],
                          actor)
    return {"genre": genre_dec, "market": market_dec}


def decisions(db, limit: int = 20) -> list[dict]:
    from app.models.phase3 import ExecutiveDecision
    rows = db.query(ExecutiveDecision).order_by(
        ExecutiveDecision.id.desc()).limit(limit).all()
    return [{"id": r.id, "question": r.question, "chosen": r.chosen,
             "rationale": r.rationale, "outcome": r.outcome,
             "options": json.loads(r.options_json or "[]")} for r in rows]


def record_decision_outcome(db, decision_id: int, outcome: str,
                            actor: str = "executive"):
    from app.models.phase3 import ExecutiveDecision
    from app.modules.memory.engine import record_outcome
    row = db.get(ExecutiveDecision, decision_id)
    if row is None:
        raise ValueError(f"decision {decision_id} not found")
    if outcome not in ("success", "failed", "pending"):
        raise ValueError("outcome must be success|failed|pending")
    row.outcome = outcome
    db.commit()
    record_outcome(db, "decision", decision_id, outcome == "success",
                   row.rationale, actor=actor)
    audit(db, actor, "decision.outcome", "decision", row.id, {"outcome": outcome})
    return row
