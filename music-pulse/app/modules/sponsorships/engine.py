"""Sponsorship Management System (Phase 2)."""
from __future__ import annotations

from app.core.audit import audit

PACKAGES = ("artist_promotion", "sponsored_ranking", "sponsored_feature",
            "newsletter", "platform")


def create_sponsor(db, name: str, contact: str = "", tier: str = "standard",
                   actor: str = "system"):
    from app.models.phase2 import Sponsor
    row = Sponsor(name=name, contact=contact, tier=tier)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "sponsor.created", "sponsor", row.id, {"name": name})
    return row


def create_campaign(db, sponsor_id: int, name: str, package: str,
                    country: str = "US", genre: str = "", budget: float = 0.0,
                    actor: str = "system"):
    from app.models.phase2 import Sponsor, Campaign
    if package not in PACKAGES:
        raise ValueError(f"unknown package: {package} (use {PACKAGES})")
    if db.get(Sponsor, sponsor_id) is None:
        raise ValueError(f"sponsor {sponsor_id} not found")
    row = Campaign(sponsor_id=sponsor_id, name=name, package=package,
                   country=country.upper(), genre=genre, budget=budget)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "campaign.created", "campaign", row.id,
          {"sponsor_id": sponsor_id, "package": package})
    return row


def record_campaign_revenue(db, campaign_id: int, amount: float,
                            actor: str = "system"):
    """Attribute revenue to a campaign (+ mirror into revenue_records)."""
    from app.models.phase2 import Campaign
    from app.modules.revenue.engine import record_revenue
    row = db.get(Campaign, campaign_id)
    if row is None:
        raise ValueError(f"campaign {campaign_id} not found")
    row.revenue = float(row.revenue or 0.0) + float(amount)
    db.commit()
    record_revenue(db, "sponsorship", amount, sponsor_id=row.sponsor_id,
                   campaign_id=row.id, country=row.country, genre=row.genre,
                   actor=actor)
    audit(db, actor, "campaign.revenue", "campaign", row.id, {"amount": amount})
    return row


def sponsor_revenue(db, sponsor_id: int) -> dict:
    from app.models.phase2 import Campaign
    rows = db.query(Campaign).filter(Campaign.sponsor_id == sponsor_id).all()
    rev = sum(float(r.revenue or 0) for r in rows)
    cost = sum(float(r.budget or 0) for r in rows)
    return {"sponsor_id": sponsor_id, "campaigns": len(rows),
            "revenue": round(rev, 2), "spend": round(cost, 2),
            "roi": round((rev - cost) / cost, 3) if cost else 0.0}


def campaign_performance(db, limit: int = 20) -> list[dict]:
    from app.models.phase2 import Campaign
    rows = db.query(Campaign).order_by(Campaign.revenue.desc()).limit(limit).all()
    out = []
    for r in rows:
        roi = ((r.revenue - r.budget) / r.budget) if r.budget else 0.0
        out.append({"id": r.id, "name": r.name, "package": r.package,
                    "budget": r.budget, "revenue": r.revenue,
                    "roi": round(roi, 3), "status": r.status})
    return out
