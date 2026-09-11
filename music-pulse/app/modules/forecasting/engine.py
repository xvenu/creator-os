"""Strategic Forecasting Engine: weekly/monthly/quarterly/annual outlooks."""
from __future__ import annotations
import json

from app.core.audit import audit

HORIZONS = ("weekly", "monthly", "quarterly", "annual")
SCOPES = ("revenue", "growth", "market", "audience")
_SCALE = {"weekly": 1, "monthly": 4, "quarterly": 13, "annual": 52}


def generate(db, scope: str = "revenue", horizon: str = "monthly",
             actor: str = "forecaster") -> dict:
    from app.models.phase4 import ForecastResult
    if scope not in SCOPES:
        raise ValueError(f"scope must be {SCOPES}")
    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be {HORIZONS}")
    base, risks = _project(db, scope)
    scale = _SCALE[horizon]
    projection = [round(base * (1 + 0.05 * i), 2) for i in range(scale)]
    row = ForecastResult(scope=scope, horizon=horizon,
                         projection_json=json.dumps(projection),
                         risks_json=json.dumps(risks))
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "forecast.generated", "forecast", row.id,
          {"scope": scope, "horizon": horizon})
    return {"id": row.id, "scope": scope, "horizon": horizon,
            "projection": projection, "risks": risks}


def _project(db, scope: str) -> tuple[float, list[str]]:
    if scope == "revenue":
        from app.modules.revenue.engine import revenue_trend
        hist = [w["total"] for w in revenue_trend(db, 4)]
        base = (sum(hist) / len(hist)) if hist else 0.0
        risks = ["sponsor churn", "platform algorithm change"] if base < 1000 else ["market saturation"]
    elif scope == "growth":
        from app.modules.acquisition.engine import FollowerGrowthTracker
        base = FollowerGrowthTracker.per_day(db) * 7
        risks = ["content fatigue"] if base < 100 else []
    elif scope == "market":
        from app.modules.market_intelligence.engine import fastest_growing
        fast = fastest_growing(db, "genre", limit=1)
        base = float(fast[0]["velocity"]) if fast else 0.0
        risks = ["genre churn"]
    else:
        from app.modules.acquisition.engine import audience_forecast
        fc = audience_forecast(db, days=30)
        base = float(fc["projected_followers"]) / 4
        risks = ["acquisition cost inflation"]
    return round(base, 2), risks


def latest(db, scope: str = "revenue", horizon: str = "monthly") -> dict | None:
    from app.models.phase4 import ForecastResult
    r = (db.query(ForecastResult)
         .filter(ForecastResult.scope == scope, ForecastResult.horizon == horizon)
         .order_by(ForecastResult.id.desc()).first())
    if not r:
        return None
    return {"scope": r.scope, "horizon": r.horizon,
            "projection": json.loads(r.projection_json or "[]"),
            "risks": json.loads(r.risks_json or "[]")}
