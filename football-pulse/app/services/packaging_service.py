"""PackagingService: assemble script + SEO + thumbnail + regions into one package."""
from __future__ import annotations

import datetime as dt

from app.services import region_service


def build_publishing_strategy(package: dict, opportunity_score: float,
                              regions: list[dict] | None = None) -> dict:
    """Rollout plan: revenue scoring → regions/language/timing/platform schedule."""
    raw = regions or region_service.rank_regions()
    scored = [
        r if isinstance(r, dict) and "monetization_score" in r
        else region_service.score_region(r["region"] if isinstance(r, dict) else str(r))
        for r in raw
    ]
    revenue = region_service.revenue_opportunity(opportunity_score, scored)
    platforms = package.get("platform_targets", ["youtube", "tiktok"])
    schedule = [
        {"platform": p, "slot": revenue["best_publish_time"], "language": revenue["best_language"]}
        for p in platforms
    ]
    return {
        "best_regions": revenue["best_regions"],
        "best_language": revenue["best_language"],
        "best_publish_time": revenue["best_publish_time"],
        "platform_schedule": schedule,
        "revenue_opportunity_score": revenue["revenue_opportunity_score"],
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def assemble_package(parts: dict) -> dict:
    """Validate all parts present → unified content package dict."""
    required = ("topic", "content_type", "script", "seo", "thumbnail", "regions")
    missing = [k for k in required if not parts.get(k)]
    if missing:
        raise ValueError(f"Package missing parts: {missing}")
    quality = parts.get("quality", {})
    return {
        "topic": parts["topic"],
        "content_type": parts["content_type"],
        "script": parts["script"],
        "seo": parts["seo"],
        "thumbnail_strategy": parts["thumbnail"],
        "target_regions": [r["region"] if isinstance(r, dict) else r for r in parts["regions"]],
        "platform_targets": parts.get("platform_targets", ["youtube", "tiktok"]),
        "quality": quality,
        "status": "assembled" if quality.get("overall_score", 0) >= 0.70 else "needs_review",
        "opportunity_score": float(parts.get("opportunity_score", 0.0)),
    }
