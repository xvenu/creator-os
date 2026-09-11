"""Timezone Optimization Engine: heatmaps, best posting times (Phase 2)."""
from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.audit import audit

# Supported scheduling zones + IANA mapping
ZONES = {
    "ET": "America/New_York",   # Eastern
    "CT": "America/Chicago",    # Central
    "MT": "America/Denver",     # Mountain
    "PT": "America/Los_Angeles",  # Pacific
    "UK": "Europe/London",
    "AU": "Australia/Sydney",
    "DE": "Europe/Berlin",
}

COUNTRY_ZONES = {
    "US": ["ET", "CT", "MT", "PT"],
    "CA": ["ET"],
    "UK": ["UK"],
    "AU": ["AU"],
    "DE": ["DE"],
}

# Default local-hour engagement curve (peaks 18-21 local); used when no data.
_DEFAULT_CURVE = {h: (0.4 + 0.6 * max(0.0, 1 - abs(h - 19.5) / 6)) for h in range(24)}


def _zones_for(country: str) -> list[str]:
    c = (country or "US").upper()
    if c not in COUNTRY_ZONES:
        raise ValueError(f"unsupported country: {country}")
    return COUNTRY_ZONES[c]


def heatmap(db, country: str = "US") -> dict[int, float]:
    """Audience activity heatmap: avg engagement per LOCAL hour (0-23).

    Uses MetricEvent.recorded_at (UTC) mapped to the country's primary zone.
    Falls back to the default curve when no data exists.
    """
    from app.models.models import MetricEvent
    zone = ZoneInfo(ZONES[_zones_for(country)[0]])
    hours: dict[int, list[int]] = {h: [] for h in range(24)}
    for ts, eng in db.query(MetricEvent.recorded_at, MetricEvent.engagement).all():
        if not ts:
            continue
        local_h = (ts.replace(tzinfo=ZoneInfo("UTC"))).astimezone(zone).hour
        hours[local_h].append(int(eng or 0))
    out: dict[int, float] = {}
    has_data = any(hours[h] for h in range(24))
    for h in range(24):
        out[h] = round(sum(hours[h]) / len(hours[h]), 2) if hours[h] else (
            0.0 if has_data else round(_DEFAULT_CURVE[h], 2))
    return out


def best_posting_times(country: str = "US", n: int = 3, db=None) -> list[dict]:
    """Top-n local hours for posting + next UTC datetime for each."""
    hm = heatmap(db, country) if db is not None else dict(_DEFAULT_CURVE)
    ranked = sorted(hm.items(), key=lambda kv: kv[1], reverse=True)[:n]
    zone = ZoneInfo(ZONES[_zones_for(country)[0]])
    now_utc = datetime.now(ZoneInfo("UTC"))
    out = []
    for hour, score in ranked:
        local_now = now_utc.astimezone(zone)
        target = local_now.replace(hour=int(hour), minute=0, second=0, microsecond=0)
        if target <= local_now:
            target += timedelta(days=1)
        out.append({"hour_local": int(hour), "zone": _zones_for(country)[0],
                    "score": score, "next_utc": target.astimezone(ZoneInfo("UTC")).isoformat()})
    return out


def schedule_for_country(country: str = "US", db=None,
                         now: datetime | None = None) -> datetime:
    """Next optimal UTC publish time for a country (naive UTC, DB-ready)."""
    best = best_posting_times(country, n=1, db=db)
    dt = datetime.fromisoformat(best[0]["next_utc"])
    return dt.replace(tzinfo=None)


def minutes_until_best(country: str = "US", db=None) -> int:
    delta = schedule_for_country(country, db=db) - datetime.utcnow()
    return max(0, int(delta.total_seconds() // 60))


def auto_reschedule(db, job_id: int, country: str = "US", actor: str = "system"):
    """Move a queued/failed job to the next peak engagement slot."""
    from app.models.models import PublishJob
    job = db.get(PublishJob, job_id)
    if job is None:
        raise ValueError(f"publish job {job_id} not found")
    job.scheduled_at = schedule_for_country(country, db=db)
    db.commit()
    db.refresh(job)
    audit(db, actor, "timezone.auto_rescheduled", "publish_job", job.id,
          {"country": country, "scheduled_at": str(job.scheduled_at)})
    return job
