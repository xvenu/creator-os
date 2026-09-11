"""ContentPlannerService: opportunities → prioritized content calendar."""
from __future__ import annotations

import datetime as dt
import hashlib

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Publish windows (UTC hours) per urgency — peak football audience slots.
PUBLISH_WINDOWS = {
    "critical": {"start": "now", "slot": " ASAP", "hours": [12, 18, 20]},
    "high": {"start": "today", "slot": "prime", "hours": [18, 20]},
    "medium": {"start": "this_week", "slot": "standard", "hours": [17]},
    "low": {"start": "backlog", "slot": "off_peak", "hours": [14]},
}

PLATFORM_BY_URGENCY = {
    "critical": ["youtube", "tiktok", "instagram"],
    "high": ["youtube", "tiktok"],
    "medium": ["tiktok", "instagram"],
    "low": ["tiktok"],
}


def make_content_id(topic: str, content_type: str) -> str:
    digest = hashlib.sha256(f"{topic.lower()}|{content_type}".encode()).hexdigest()[:10]
    return f"ct-{digest}"


def plan_item(opportunity: dict) -> dict:
    """Single opportunity → calendar entry."""
    urgency = str(opportunity.get("urgency", "medium"))
    if urgency not in PRIORITY_ORDER:
        urgency = "medium"
    topic = str(opportunity.get("topic", opportunity.get("title", "untitled")))
    content_type = str(opportunity.get("content_type", "short"))
    platforms = opportunity.get("target_platforms") or PLATFORM_BY_URGENCY[urgency]
    reach = int(opportunity.get("estimated_reach", 0))
    return {
        "content_id": make_content_id(topic, content_type),
        "topic": topic,
        "content_type": content_type,
        "publish_priority": urgency,
        "publish_window": {"urgency": urgency, **PUBLISH_WINDOWS[urgency]},
        "platform_targets": platforms,
        "expected_reach": reach,
        "status": "scheduled",
    }


def build_calendar(opportunities: list[dict], limit: int = 20) -> list[dict]:
    """Rank by (urgency, score) and assign queue positions."""
    planned = [plan_item(o) for o in opportunities]
    planned.sort(key=lambda p: (
        PRIORITY_ORDER[p["publish_priority"]],
        -float(next((o.get("score", 0) for o in opportunities
                     if o.get("topic", o.get("title")) == p["topic"]), 0)),
    ))
    for i, entry in enumerate(planned[:limit]):
        entry["queue_position"] = i + 1
    return planned[:limit]


def next_publish_slot(urgency: str, now: dt.datetime | None = None) -> str:
    """Next UTC slot label for an urgency level (deterministic)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    hours = PUBLISH_WINDOWS.get(urgency, PUBLISH_WINDOWS["medium"])["hours"]
    for h in sorted(hours):
        if now.hour < h:
            return f"{now.date()} {h:02d}:00 UTC"
    return f"{now.date() + dt.timedelta(days=1)} {min(hours):02d}:00 UTC"
