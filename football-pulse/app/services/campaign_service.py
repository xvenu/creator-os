"""CampaignService: discover, evaluate, score and rank clipping campaigns.

Deterministic scoring documented below. Categories:
football | sports | gaming | entertainment | general.
"""
from __future__ import annotations

VALID_NICHES = ("football", "sports", "gaming", "entertainment", "general")

# Niche alignment with FootballPulse audience (0..1).
NICHE_WEIGHTS: dict[str, float] = {
    "football": 1.0,
    "sports": 0.8,
    "entertainment": 0.6,
    "gaming": 0.5,
    "general": 0.4,
}

# Payout-model risk: higher = riskier/less predictable income.
PAYOUT_MODEL_RISK: dict[str, float] = {
    "fixed": 0.15,
    "hybrid": 0.35,
    "rev_share": 0.5,
    "per_view": 0.55,
    "performance": 0.6,
    "unknown": 0.7,
}

PLATFORM_REACH: dict[str, float] = {
    "tiktok": 1.0,
    "youtube": 0.95,
    "instagram": 0.85,
    "x": 0.7,
    "telegram": 0.5,
}

RECOMMEND_MIN_SCORE = 0.6
RECOMMEND_MAX_RISK = 0.7


def normalize_niche(niche: str) -> str:
    key = (niche or "").strip().lower()
    return key if key in VALID_NICHES else "general"


def discover_campaigns(raw_listings: list[dict]) -> list[dict]:
    """Normalize raw campaign listings → validated campaign dicts."""
    out = []
    for raw in raw_listings:
        name = str(raw.get("campaign_name", "")).strip()
        if not name:
            continue
        out.append(
            {
                "campaign_name": name,
                "platform": str(raw.get("platform", "tiktok")).strip().lower(),
                "payout_model": str(raw.get("payout_model", "unknown")).strip().lower(),
                "payout_estimate": max(float(raw.get("payout_estimate", 0.0) or 0.0), 0.0),
                "requirements": dict(raw.get("requirements", {})),
                "niche": normalize_niche(str(raw.get("niche", "football"))),
                "active": bool(raw.get("active", True)),
                "countries": list(raw.get("countries", [])),
                "url": raw.get("url"),
            }
        )
    return out


def payout_score(payout_estimate: float) -> float:
    """Log-scaled 0..1 payout signal (calibrated: $500 ≈ 0.85)."""
    if payout_estimate <= 0:
        return 0.0
    import math

    return round(min(math.log10(1 + payout_estimate) / math.log10(1 + 1000), 1.0), 3)


def risk_score(campaign: dict) -> float:
    """0..1 risk from payout model + requirement strictness + geo limits.

    Strictness signals: min_followers ≥10k (+0.15), exclusivity (+0.15),
    geo-restricted (not global, +0.1), upfront_fee (+0.2).
    """
    model = str(campaign.get("payout_model", "unknown")).lower()
    base = PAYOUT_MODEL_RISK.get(model, 0.7)
    req = campaign.get("requirements", {}) or {}
    strictness = 0.0
    try:
        if int(req.get("min_followers", 0) or 0) >= 10_000:
            strictness += 0.15
    except (TypeError, ValueError):
        pass
    if req.get("exclusivity"):
        strictness += 0.15
    if req.get("upfront_fee"):
        strictness += 0.2
    countries = [c.lower() for c in (campaign.get("countries", []) or [])]
    if countries and not any(c in ("global", "worldwide") for c in countries):
        strictness += 0.1
    return round(min(base + strictness, 1.0), 3)


def roi_estimate(campaign: dict, risk: float) -> float:
    """Expected monthly value = payout × (1 − risk) × niche multiplier."""
    niche = normalize_niche(str(campaign.get("niche", "general")))
    return round(float(campaign.get("payout_estimate", 0.0)) * (1.0 - risk) * NICHE_WEIGHTS[niche], 2)


def score_campaign(campaign: dict) -> dict:
    """Full evaluation → opportunity dict with score, roi, risk, recommendation."""
    niche = normalize_niche(str(campaign.get("niche", "general")))
    platform = str(campaign.get("platform", "")).lower()
    risk = risk_score(campaign)
    roi = roi_estimate(campaign, risk)
    score = round(
        payout_score(float(campaign.get("payout_estimate", 0.0))) * 0.45
        + NICHE_WEIGHTS[niche] * 0.3
        + PLATFORM_REACH.get(platform, 0.5) * 0.15
        + (1.0 - risk) * 0.1,
        3,
    )
    active = bool(campaign.get("active", True))
    recommended = bool(active and score >= RECOMMEND_MIN_SCORE and risk <= RECOMMEND_MAX_RISK)
    rationale = (
        f"{campaign.get('campaign_name')} [{niche}/{platform}]: "
        f"payout={campaign.get('payout_estimate')}, score={score}, "
        f"risk={risk}, roi={roi}, active={active}."
    )
    return {
        "campaign_name": campaign.get("campaign_name"),
        "platform": platform,
        "payout_model": campaign.get("payout_model"),
        "payout_estimate": campaign.get("payout_estimate", 0.0),
        "requirements": campaign.get("requirements", {}),
        "niche": niche,
        "active": active,
        "score": score,
        "roi_estimate": roi,
        "risk_score": risk,
        "recommended": recommended,
        "rationale": rationale,
    }


def evaluate_campaign(campaign: dict) -> dict:
    return score_campaign(campaign)


def rank_opportunities(campaigns: list[dict], limit: int = 20) -> list[dict]:
    """Score + sort campaigns by opportunity score (desc)."""
    scored = [score_campaign(c) for c in campaigns]
    return sorted(scored, key=lambda o: o["score"], reverse=True)[:limit]
