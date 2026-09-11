"""Revenue Analytics Engine (Phase 2)."""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import func

from app.core.audit import audit

SOURCES = ("sponsorship", "affiliate", "promotion", "platform")


def record_revenue(db, source_type: str, amount: float, sponsor_id: int = 0,
                   campaign_id: int = 0, country: str = "US", genre: str = "",
                   platform: str = "", actor: str = "system"):
    from app.models.phase2 import RevenueRecord
    if source_type not in SOURCES:
        raise ValueError(f"unknown source: {source_type} (use {SOURCES})")
    row = RevenueRecord(source_type=source_type, amount=float(amount),
                        sponsor_id=sponsor_id, campaign_id=campaign_id,
                        country=country.upper(), genre=genre, platform=platform)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "revenue.recorded", "revenue", row.id,
          {"source": source_type, "amount": amount})
    return row


def _total(db, **filters) -> float:
    from app.models.phase2 import RevenueRecord
    q = db.query(func.coalesce(func.sum(RevenueRecord.amount), 0.0))
    for k, v in filters.items():
        q = q.filter(getattr(RevenueRecord, k) == v)
    return float(q.scalar() or 0.0)


def mrr(db) -> dict:
    """Monthly recurring revenue: last-30d total + target progress."""
    from app.models.phase2 import RevenueRecord
    from app.core.config import get_settings
    total = float(db.query(func.coalesce(func.sum(RevenueRecord.amount), 0.0)).filter(
        RevenueRecord.recorded_at >= datetime.utcnow() - timedelta(days=30)
    ).scalar() or 0.0)
    target = get_settings().mrr_target
    return {"mrr_30d": round(total, 2), "target": target,
            "progress": round(total / target, 3) if target else 0.0}


def revenue_by(db, dimension: str) -> list[dict]:
    """Revenue grouped by country | genre | platform | source_type."""
    from app.models.phase2 import RevenueRecord
    col = {"country": RevenueRecord.country, "genre": RevenueRecord.genre,
           "platform": RevenueRecord.platform,
           "source": RevenueRecord.source_type}.get(dimension)
    if col is None:
        raise ValueError("dimension must be country|genre|platform|source")
    rows = (db.query(col, func.sum(RevenueRecord.amount).label("total"))
            .group_by(col).order_by(func.sum(RevenueRecord.amount).desc()).all())
    return [{"key": k or "unknown", "total": round(float(t or 0), 2)} for k, t in rows]


def revenue_trend(db, weeks: int = 8) -> list[dict]:
    from app.models.phase2 import RevenueRecord
    now = datetime.utcnow()
    out = []
    for w in range(weeks):
        lo, hi = now - timedelta(days=7 * (w + 1)), now - timedelta(days=7 * w)
        v = float(db.query(func.coalesce(func.sum(RevenueRecord.amount), 0.0)).filter(
            RevenueRecord.recorded_at >= lo, RevenueRecord.recorded_at < hi
        ).scalar() or 0.0)
        out.append({"week_start": str(lo.date()), "total": round(v, 2)})
    out.reverse()
    return out


def revenue_forecast(db, weeks: int = 4) -> dict:
    hist = revenue_trend(db, 8)
    vals = [w["total"] for w in hist]
    slope = (vals[-1] - vals[0]) / max(len(vals) - 1, 1) if vals else 0.0
    proj = [round(max(vals[-1] + slope * (i + 1), 0), 2) for i in range(weeks)] if vals else [0.0] * weeks
    return {"history": vals, "projection": proj}


def leaderboard(db, dimension: str = "country", limit: int = 10) -> list[dict]:
    return revenue_by(db, dimension)[:limit]


def summary(db) -> dict:
    return {"total": round(_total(db), 2), "mrr": mrr(db),
            "by_country": revenue_by(db, "country"),
            "by_genre": revenue_by(db, "genre"),
            "by_platform": revenue_by(db, "platform"),
            "by_source": revenue_by(db, "source")}
