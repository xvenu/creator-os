"""ContentOpportunityService: intelligence → scored content opportunities.

Content types: short | long_form | transfer_update | match_preview |
match_review | tactical_breakdown | documentary.
"""
from __future__ import annotations

VALID_CONTENT_TYPES = (
    "short",
    "long_form",
    "transfer_update",
    "match_preview",
    "match_review",
    "tactical_breakdown",
    "documentary",
)

VALID_SOURCE_KINDS = ("news", "transfer", "prediction", "campaign", "match")

# Source-kind base weights: how naturally a signal converts to content.
SOURCE_WEIGHTS = {
    "transfer": 0.9,
    "prediction": 0.85,
    "match": 0.85,
    "news": 0.75,
    "campaign": 0.6,
}

URGENCY_BY_SCORE = ((0.8, "critical"), (0.6, "high"), (0.4, "medium"), (0.0, "low"))

VALUE_PER_1K_VIEWS = 4.0  # blended $ RPM assumption, documented


def create_opportunity(item: dict) -> dict:
    """Build an unscored opportunity from an intelligence item.

    Required: title, topic. Optional: source_kind, signals{...}, content_type.
    """
    title = str(item.get("title", "")).strip()
    if not title:
        raise ValueError("Opportunity requires a title")
    source_kind = str(item.get("source_kind", "news")).lower()
    if source_kind not in VALID_SOURCE_KINDS:
        raise ValueError(f"Unknown source kind: {source_kind}")
    content_type = item.get("content_type") or _default_content_type(source_kind, item.get("status"))
    if content_type not in VALID_CONTENT_TYPES:
        raise ValueError(f"Unknown content type: {content_type}")
    return {
        "title": title,
        "topic": str(item.get("topic", title)).strip(),
        "source_kind": source_kind,
        "content_type": content_type,
        "signals": dict(item.get("signals", {})),
        "meta": dict(item.get("meta", {})),
    }


def _default_content_type(source_kind: str, status: str | None) -> str:
    if source_kind == "transfer":
        return "transfer_update"
    if source_kind == "prediction":
        return "match_preview"
    if source_kind == "match":
        return "match_review" if status == "completed" else "match_preview"
    if source_kind == "campaign":
        return "short"
    return "short"


def score_opportunity(opportunity: dict) -> dict:
    """Score 0..1: source weight × signal strength + urgency signals.

    signal strength = mean of provided signal values (0..1 each).
    breaking=True adds +0.15, kickoff_soon/imminent adds +0.10 (capped 1.0).
    """
    signals = opportunity.get("signals", {}) or {}
    values = [float(v) for v in signals.values() if isinstance(v, (int, float))]
    strength = sum(values) / len(values) if values else 0.3
    source_w = SOURCE_WEIGHTS[opportunity["source_kind"]]
    score = source_w * 0.55 + strength * 0.45
    meta = opportunity.get("meta", {}) or {}
    if meta.get("breaking"):
        score += 0.15
    if meta.get("imminent"):
        score += 0.10
    score = round(max(0.0, min(score, 1.0)), 3)
    urgency = next(label for threshold, label in URGENCY_BY_SCORE if score >= threshold)
    return {**opportunity, "score": score, "urgency": urgency}


def estimate_value(score: float, urgency: str, platforms: list[str]) -> dict:
    """Reach + $ value from score, urgency and platform mix."""
    urgency_mult = {"critical": 1.5, "high": 1.2, "medium": 0.9, "low": 0.6}[urgency]
    platform_mult = sum(
        {"youtube": 1.0, "tiktok": 1.3, "instagram": 1.0, "x": 0.5, "telegram": 0.3}.get(p, 0.5)
        for p in platforms
    ) or 0.5
    reach = int(8_000 * score * urgency_mult * platform_mult)
    value = round(reach / 1000 * VALUE_PER_1K_VIEWS, 2)
    return {"estimated_reach": reach, "estimated_value": value}


def rank_opportunities(opportunities: list[dict], limit: int = 20) -> list[dict]:
    scored = [score_opportunity(o) for o in opportunities]
    return sorted(scored, key=lambda o: o["score"], reverse=True)[:limit]
