"""Revenue Execution Engine: execute monetization plans, track performance."""
from __future__ import annotations

from app.core.audit import audit


def plan_actions(db, actor: str = "executor") -> list[dict]:
    """Turn optimizer output into executable revenue actions."""
    from app.models.phase4 import RevenueAction
    from app.modules.revenue_optimizer.engine import results as opt_results
    recs = opt_results(db, 5)
    out = []
    for r in recs:
        row = RevenueAction(action=f"{r['scope']}: {r['recommendation'][:120]}",
                            amount=float(r["expected_uplift"] or 0))
        db.add(row)
        out.append({"scope": r["scope"], "amount": row.amount})
    db.commit()
    audit(db, actor, "revenue.planned", "revenue_action", "", {"count": len(out)})
    return out


def execute_action(db, action_id: int, campaign_id: int = 0, actor: str = "executor"):
    from app.models.phase4 import RevenueAction
    from app.modules.revenue.engine import record_revenue
    row = db.get(RevenueAction, action_id)
    if row is None:
        raise ValueError(f"action {action_id} not found")
    row.campaign_id = campaign_id
    row.status = "executed"
    db.commit()
    if row.amount:
        record_revenue(db, "promotion", row.amount, campaign_id=campaign_id,
                       actor=actor)
    audit(db, actor, "revenue.executed", "revenue_action", row.id,
          {"amount": row.amount})
    return row


def active_campaigns(db) -> list[dict]:
    from app.models.phase2 import Campaign
    rows = db.query(Campaign).filter(Campaign.status == "active").all()
    return [{"id": r.id, "name": r.name, "package": r.package,
             "budget": r.budget, "revenue": r.revenue} for r in rows]


def utilization(db) -> dict:
    from app.models.phase2 import Campaign
    rows = db.query(Campaign).all()
    rev = sum(float(r.revenue or 0) for r in rows)
    bud = sum(float(r.budget or 0) for r in rows)
    return {"campaigns": len(rows), "revenue": round(rev, 2),
            "spend": round(bud, 2),
            "utilization": round(rev / bud, 3) if bud else 0.0}


def forecast(db, weeks: int = 4) -> dict:
    from app.modules.revenue.engine import revenue_forecast
    return revenue_forecast(db, weeks)
