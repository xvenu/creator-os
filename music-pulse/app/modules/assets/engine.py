"""Asset Ownership Engine: track, value, expand owned assets."""
from __future__ import annotations

from app.core.audit import audit

KINDS = ("website", "domain", "newsletter", "community", "database", "product")


def register_asset(db, name: str, kind: str, traffic: int = 0, revenue: float = 0.0,
                   growth: float = 0.0, engagement: float = 0.0, actor: str = "assets"):
    from app.models.phase4 import OwnedAsset
    if kind not in KINDS:
        raise ValueError(f"kind must be {KINDS}")
    row = OwnedAsset(name=name, kind=kind, traffic=traffic, revenue=revenue,
                     growth=growth, engagement=engagement,
                     valuation=_value(traffic, revenue, growth, engagement))
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "asset.registered", "asset", row.id, {"name": name})
    return row


def _value(traffic: int, revenue: float, growth: float, engagement: float) -> float:
    return round(revenue * 12 * (1 + max(growth, 0)) + traffic * 0.10 * (1 + engagement), 2)


def update_asset(db, asset_id: int, actor: str = "assets", **fields):
    from app.models.phase4 import OwnedAsset
    row = db.get(OwnedAsset, asset_id)
    if row is None:
        raise ValueError(f"asset {asset_id} not found")
    for k in ("traffic", "revenue", "growth", "engagement"):
        if k in fields:
            setattr(row, k, fields[k])
    row.valuation = _value(row.traffic, row.revenue, row.growth, row.engagement)
    db.commit()
    db.refresh(row)
    audit(db, actor, "asset.updated", "asset", row.id, fields)
    return row


def performance_report(db) -> list[dict]:
    from app.models.phase4 import OwnedAsset
    rows = db.query(OwnedAsset).order_by(OwnedAsset.revenue.desc()).all()
    return [{"id": r.id, "name": r.name, "kind": r.kind, "traffic": r.traffic,
             "revenue": r.revenue, "growth": r.growth,
             "engagement": r.engagement} for r in rows]


def valuation_report(db) -> list[dict]:
    from app.models.phase4 import OwnedAsset
    rows = db.query(OwnedAsset).order_by(OwnedAsset.valuation.desc()).all()
    total = sum(float(r.valuation or 0) for r in rows)
    return {"total_valuation": round(total, 2),
            "assets": [{"name": r.name, "valuation": r.valuation} for r in rows]}


def expansion_opportunities(db, limit: int = 5) -> list[dict]:
    from app.models.phase4 import OwnedAsset
    rows = (db.query(OwnedAsset).order_by(OwnedAsset.growth.desc()).limit(limit).all())
    return [{"asset": r.name, "growth": r.growth,
             "suggestion": f"double down on '{r.name}' — highest growth; "
                           "clone format to adjacent genre/region"} for r in rows]
