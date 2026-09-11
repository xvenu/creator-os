"""ExecutiveService: CEO-level opportunity evaluation and recommendations.

Decision model — weighted opportunity score from 5 intelligence signals:
- news importance ........ 25%
- transfer credibility ... 20%
- prediction confidence .. 20%
- campaign ROI (0..1) .... 15%
- trend score ............ 20%

Tiers: ≥0.80 immediate · 0.60–0.79 create · 0.40–0.59 monitor · <0.40 ignore.
"""
from __future__ import annotations

WEIGHTS = {
    "news_importance": 0.25,
    "transfer_credibility": 0.20,
    "prediction_confidence": 0.20,
    "campaign_roi": 0.15,
    "trend_score": 0.20,
}

TIER_IMMEDIATE = "immediate"
TIER_CREATE = "create"
TIER_MONITOR = "monitor"
TIER_IGNORE = "ignore"

PRIORITY_MAP = {
    TIER_IMMEDIATE: "critical",
    TIER_CREATE: "high",
    TIER_MONITOR: "medium",
    TIER_IGNORE: "low",
}

PLATFORM_MULTIPLIERS = {
    "youtube": 1.0,
    "tiktok": 1.4,
    "instagram": 1.1,
    "x": 0.7,
    "telegram": 0.4,
}

BASE_REACH = 10_000


def evaluate_opportunity(signals: dict) -> dict:
    """Weighted 0..1 opportunity score + tier + priority.

    Phase 4: an optional `revenue_opportunity_score` signal (0..1, from the
    Region Monetization Engine) blends in at 15% weight — absent by default,
    so Phase 3 behavior is unchanged.
    """
    score = round(
        sum(float(signals.get(k, 0.0) or 0.0) * w for k, w in WEIGHTS.items()),
        3,
    )
    revenue = signals.get("revenue_opportunity_score")
    if revenue is not None:
        score = round(0.85 * score + 0.15 * max(0.0, min(float(revenue), 1.0)), 3)
    score = max(0.0, min(score, 1.0))
    if score >= 0.80:
        tier = TIER_IMMEDIATE
    elif score >= 0.60:
        tier = TIER_CREATE
    elif score >= 0.40:
        tier = TIER_MONITOR
    else:
        tier = TIER_IGNORE
    return {
        "opportunity_score": score,
        "tier": tier,
        "priority_level": PRIORITY_MAP[tier],
        "urgency": "critical" if tier == TIER_IMMEDIATE else ("high" if tier == TIER_CREATE else ("medium" if tier == TIER_MONITOR else "low")),
    }


def prioritize_opportunities(evaluated: list[dict]) -> list[dict]:
    """Sort by tier rank, then score, then urgency weight."""
    tier_rank = {TIER_IMMEDIATE: 0, TIER_CREATE: 1, TIER_MONITOR: 2, TIER_IGNORE: 3}
    urgency_w = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    return sorted(
        evaluated,
        key=lambda o: (
            tier_rank.get(o.get("tier", TIER_IGNORE), 3),
            -float(o.get("opportunity_score", 0.0)),
            -urgency_w.get(o.get("urgency", "low"), 0),
        ),
    )


def _select_platforms(score: float, source_kind: str) -> list[str]:
    if score >= 0.80:
        return ["youtube", "tiktok", "instagram"]
    if score >= 0.60:
        return ["youtube", "tiktok"] if source_kind in ("match", "prediction") else ["tiktok", "instagram"]
    if score >= 0.40:
        return ["tiktok"]
    return ["x"]


def _select_content_type(source_kind: str, status: str | None) -> str:
    mapping = {
        "transfer": "transfer_update",
        "prediction": "match_preview",
        "campaign": "short",
        "news": "short",
    }
    if source_kind == "match":
        return "match_review" if status == "completed" else "match_preview"
    return mapping.get(source_kind, "short")


def generate_recommendation(context: dict) -> dict:
    """Answer the 5 CEO questions: create? trending? urgent? platforms? type?"""
    score = float(context.get("opportunity_score", 0.0))
    tier = context.get("tier", TIER_IGNORE)
    trend = float(context.get("trend_score", 0.0))
    source_kind = str(context.get("source_kind", "news"))
    status = context.get("status")
    should_create = tier in (TIER_IMMEDIATE, TIER_CREATE)
    return {
        "should_create_content": should_create,
        "is_trending": trend >= 0.5,
        "is_urgent": tier == TIER_IMMEDIATE,
        "target_platforms": _select_platforms(score, source_kind),
        "content_type": _select_content_type(source_kind, status),
        "action": (
            "produce immediately" if tier == TIER_IMMEDIATE
            else "schedule production" if tier == TIER_CREATE
            else "keep monitoring" if tier == TIER_MONITOR
            else "no action"
        ),
    }


def estimate_reach(score: float, trend: float, platforms: list[str]) -> int:
    """Expected views: base × score × (1+trend) × summed platform multipliers."""
    mult = sum(PLATFORM_MULTIPLIERS.get(p, 0.5) for p in platforms) or 0.5
    return int(BASE_REACH * (0.3 + score) * (1.0 + trend) * mult)


def estimate_engagement(score: float, trend: float) -> float:
    """Expected engagement rate 0..1: base 3% scaled by score and trend."""
    return round(min(0.03 * (0.5 + score) * (1.0 + trend), 0.25), 4)


def decide(context: dict) -> dict:
    """Full decision: score → tier → recommendation → reach/engagement + reasoning."""
    signals = context.get("signals", {}) or {}
    evaluation = evaluate_opportunity(signals)
    merged = {**context, **evaluation, "trend_score": float(signals.get("trend_score", 0.0))}
    recommendation = generate_recommendation(merged)
    reach = estimate_reach(
        evaluation["opportunity_score"],
        float(context.get("signals", {}).get("trend_score", 0.0)),
        recommendation["target_platforms"],
    )
    engagement = estimate_engagement(
        evaluation["opportunity_score"],
        float(context.get("signals", {}).get("trend_score", 0.0)),
    )
    parts = [
        f"score={evaluation['opportunity_score']:.2f} ({evaluation['tier']})",
        f"action: {recommendation['action']}",
        f"type: {recommendation['content_type']} → {', '.join(recommendation['target_platforms'])}",
    ]
    return {
        **evaluation,
        "recommendation": recommendation,
        "expected_reach": reach,
        "expected_engagement": engagement,
        "reasoning": "; ".join(parts) + ".",
    }
