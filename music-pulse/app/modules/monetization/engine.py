"""Autonomous Monetization Engine: match, price, allocate, optimize."""
from __future__ import annotations
import json

from app.core.audit import audit

RULE_TYPES = ("sponsor_match", "pricing", "affiliate", "inventory")


class SponsorMatcher:
    @staticmethod
    def match(db, genre: str = "", country: str = "US", limit: int = 5) -> list[dict]:
        from app.models.phase2 import Sponsor, Campaign
        sponsors = db.query(Sponsor).filter(Sponsor.active.is_(True)).all()
        scored = []
        for s in sponsors:
            n = db.query(Campaign).filter(Campaign.sponsor_id == s.id).count()
            genre_camps = db.query(Campaign).filter(
                Campaign.sponsor_id == s.id, Campaign.genre == genre).count() if genre else 0
            score = round(n * 10 + genre_camps * 25 + (5 if s.tier == "premium" else 0), 2)
            scored.append({"sponsor_id": s.id, "name": s.name, "tier": s.tier,
                           "score": score,
                           "reason": f"{n} past campaigns, {genre_camps} in {genre or 'any'}"})
        scored.sort(key=lambda d: d["score"], reverse=True)
        return scored[:limit]


class PricingEngine:
    @staticmethod
    def price(db, package: str, genre: str = "", country: str = "US") -> dict:
        from app.modules.profitability.engine import profitability_score
        base = {"artist_promotion": 500, "sponsored_ranking": 800,
                "sponsored_feature": 1200, "newsletter": 400,
                "platform": 2000}.get(package, 500)
        try:
            prof = profitability_score(db, genre or "Pop", country).get("score", 50)
        except Exception:
            prof = 50.0
        multiplier = 0.5 + (prof / 100)
        country_mult = {"US": 1.0, "UK": 0.9, "CA": 0.85, "AU": 0.8, "DE": 0.85}.get(
            country.upper(), 0.8)
        price = round(base * multiplier * country_mult, 2)
        return {"package": package, "price": price,
                "rationale": f"base ${base} x profitability {prof} x {country}"}


class AffiliateOptimizer:
    OFFERS = ({"offer": "streaming-trial", "payout": 3.0, "genres": ["Pop", "Hip-Hop"]},
              {"offer": "concert-tickets", "payout": 8.0, "genres": ["Country", "Rock"]},
              {"offer": "merch-store", "payout": 5.0, "genres": ["K-Pop", "Indie"]},
              {"offer": "audio-gear", "payout": 12.0, "genres": ["EDM", "Hip-Hop"]})

    @classmethod
    def select(cls, genre: str = "", limit: int = 3) -> list[dict]:
        ranked = sorted(cls.OFFERS,
                        key=lambda o: (genre in o["genres"], o["payout"]),
                        reverse=True)
        return [{"offer": o["offer"], "payout": o["payout"]} for o in ranked[:limit]]


class InventoryManager:
    @staticmethod
    def utilization(db) -> dict:
        from app.models.phase2 import Campaign
        from app.modules.sponsorships.engine import PACKAGES
        rows = db.query(Campaign).all()
        used = {p: 0 for p in PACKAGES}
        for r in rows:
            if r.package in used:
                used[r.package] += 1
        capacity = 10  # slots per package per cycle
        return {"used": used, "capacity": capacity,
                "available": {p: capacity - used[p] for p in PACKAGES}}


class CampaignAllocator:
    @staticmethod
    def allocate(db, sponsor_id: int, genre: str = "Pop", country: str = "US",
                 actor: str = "monetization") -> dict:
        from app.modules.sponsorships.engine import create_campaign
        inv = InventoryManager.utilization(db)
        package = max(inv["available"], key=inv["available"].get)
        pricing = PricingEngine.price(db, package, genre, country)
        camp = create_campaign(db, sponsor_id, f"Auto {package} {genre}",
                               package, country, genre,
                               budget=pricing["price"], actor=actor)
        return {"campaign_id": camp.id, "package": package,
                "budget": pricing["price"]}


def upsert_rule(db, name: str, rule_type: str, config: dict | None = None,
                actor: str = "monetization"):
    from app.models.phase4 import MonetizationRule
    if rule_type not in RULE_TYPES:
        raise ValueError(f"rule_type must be {RULE_TYPES}")
    row = db.query(MonetizationRule).filter(MonetizationRule.name == name).first()
    if row is None:
        row = MonetizationRule(name=name, rule_type=rule_type)
        db.add(row)
    row.config_json = json.dumps(config or {})
    db.commit()
    db.refresh(row)
    audit(db, actor, "monetization.rule", "rule", row.id, {"name": name})
    return row
