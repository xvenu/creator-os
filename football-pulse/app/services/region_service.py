"""RegionIntelligenceService: monetization-ranked regions + revenue scoring.

Tiers: 1 = premium CPM (US/UK/CA/AU/DE/NL/NO/CH), 2 = strong EU (FR/BE/AT/
DK/SE/IE), 3 = remaining global markets. Lower tiers can still surface via
audience quality — tier is a boost, not a gate.

Revenue Opportunity Score = Opportunity Score × Monetization × Audience Quality.
"""
from __future__ import annotations

# region: (tier, cpm $, rpm $, football_interest 0..1, language, publish_time UTC)
REGIONS: dict[str, dict] = {
    "US": {"tier": 1, "cpm": 18.0, "rpm": 9.0, "interest": 0.65, "language": "en", "publish_time": "00:00 UTC"},
    "UK": {"tier": 1, "cpm": 15.0, "rpm": 7.5, "interest": 0.95, "language": "en", "publish_time": "18:00 UTC"},
    "Canada": {"tier": 1, "cpm": 14.0, "rpm": 7.0, "interest": 0.55, "language": "en", "publish_time": "00:00 UTC"},
    "Australia": {"tier": 1, "cpm": 13.0, "rpm": 6.5, "interest": 0.60, "language": "en", "publish_time": "09:00 UTC"},
    "Germany": {"tier": 1, "cpm": 12.0, "rpm": 6.0, "interest": 0.90, "language": "de", "publish_time": "18:00 UTC"},
    "Netherlands": {"tier": 1, "cpm": 12.0, "rpm": 6.0, "interest": 0.85, "language": "nl", "publish_time": "18:00 UTC"},
    "Norway": {"tier": 1, "cpm": 13.0, "rpm": 6.5, "interest": 0.80, "language": "no", "publish_time": "18:00 UTC"},
    "Switzerland": {"tier": 1, "cpm": 14.0, "rpm": 7.0, "interest": 0.70, "language": "de", "publish_time": "18:00 UTC"},
    "France": {"tier": 2, "cpm": 10.0, "rpm": 5.0, "interest": 0.90, "language": "fr", "publish_time": "18:00 UTC"},
    "Belgium": {"tier": 2, "cpm": 10.0, "rpm": 5.0, "interest": 0.85, "language": "fr", "publish_time": "18:00 UTC"},
    "Austria": {"tier": 2, "cpm": 9.0, "rpm": 4.5, "interest": 0.80, "language": "de", "publish_time": "18:00 UTC"},
    "Denmark": {"tier": 2, "cpm": 11.0, "rpm": 5.5, "interest": 0.85, "language": "da", "publish_time": "18:00 UTC"},
    "Sweden": {"tier": 2, "cpm": 11.0, "rpm": 5.5, "interest": 0.85, "language": "sv", "publish_time": "18:00 UTC"},
    "Ireland": {"tier": 2, "cpm": 12.0, "rpm": 6.0, "interest": 0.90, "language": "en", "publish_time": "18:00 UTC"},
    "Spain": {"tier": 3, "cpm": 7.0, "rpm": 3.5, "interest": 0.95, "language": "es", "publish_time": "19:00 UTC"},
    "Italy": {"tier": 3, "cpm": 7.0, "rpm": 3.5, "interest": 0.95, "language": "it", "publish_time": "19:00 UTC"},
    "Brazil": {"tier": 3, "cpm": 4.0, "rpm": 2.0, "interest": 1.0, "language": "pt", "publish_time": "22:00 UTC"},
    "Nigeria": {"tier": 3, "cpm": 2.5, "rpm": 1.2, "interest": 1.0, "language": "en", "publish_time": "18:00 UTC"},
    "India": {"tier": 3, "cpm": 2.0, "rpm": 1.0, "interest": 0.85, "language": "en", "publish_time": "14:00 UTC"},
    "Indonesia": {"tier": 3, "cpm": 2.0, "rpm": 1.0, "interest": 0.90, "language": "id", "publish_time": "12:00 UTC"},
}

TIER_BOOST = {1: 1.0, 2: 0.9, 3: 0.75}
MAX_CPM = 18.0


def monetization_score(region: str) -> float:
    data = REGIONS.get(region)
    if not data:
        raise ValueError(f"Unknown region: {region}")
    return round((data["cpm"] / MAX_CPM) * 0.6 + data["interest"] * 0.4, 3)


def audience_quality(region: str) -> float:
    """Engagement propensity: football interest blended with tier retention."""
    data = REGIONS.get(region)
    if not data:
        raise ValueError(f"Unknown region: {region}")
    tier_retention = {1: 0.9, 2: 0.8, 3: 0.7}[data["tier"]]
    return round(data["interest"] * 0.7 + tier_retention * 0.3, 3)


def score_region(region: str) -> dict:
    data = REGIONS[region]
    monetization = monetization_score(region)
    quality = audience_quality(region)
    composite = round(monetization * 0.55 + quality * 0.45, 3)
    return {
        "region": region,
        "tier": data["tier"],
        "cpm_estimate": data["cpm"],
        "rpm_estimate": data["rpm"],
        "football_interest": data["interest"],
        "recommended_language": data["language"],
        "recommended_publish_time": data["publish_time"],
        "monetization_score": monetization,
        "audience_quality": quality,
        "composite_score": composite,
    }


def rank_regions(limit: int = 8, ensure_tier_mix: bool = True) -> list[dict]:
    """Top regions by composite; guarantees tier-2/3 representation when enabled."""
    ranked = sorted((score_region(r) for r in REGIONS), key=lambda r: r["composite_score"], reverse=True)
    top = ranked[:limit]
    if ensure_tier_mix:
        tiers = {r["tier"] for r in top}
        if 2 not in tiers and 3 not in tiers:
            # Swap the last slot for the best non-tier-1 region.
            alt = next(r for r in ranked if r["tier"] in (2, 3))
            top = [*top[:-1], alt]
    return top


def revenue_opportunity(opportunity_score: float, region_scores: list[dict]) -> dict:
    """Revenue Opportunity = Opportunity × Monetization × Audience Quality (best region)."""
    if not region_scores:
        raise ValueError("Need at least one scored region")
    best = max(region_scores,
               key=lambda r: opportunity_score * r["monetization_score"] * r["audience_quality"])
    score = round(opportunity_score * best["monetization_score"] * best["audience_quality"], 4)
    return {
        "revenue_opportunity_score": score,
        "best_regions": [r["region"] for r in sorted(
            region_scores, key=lambda r: r["monetization_score"] * r["audience_quality"],
            reverse=True)[:3]],
        "best_language": best["recommended_language"],
        "best_publish_time": best["recommended_publish_time"],
    }
