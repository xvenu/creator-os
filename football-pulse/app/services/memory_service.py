"""MemoryService: automatic long-term memory updates from intelligence.

Memory kinds (Phase 2):
- trending_clubs / trending_players / trending_competitions
- recurring_transfer_targets / recurring_campaign_opportunities

value shape: {"count": int, ...extra}. confidence ramps with repetitions.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Memory

TRENDING_CLUBS = "trending_clubs"
TRENDING_PLAYERS = "trending_players"
TRENDING_COMPETITIONS = "trending_competitions"
RECURRING_TRANSFER_TARGETS = "recurring_transfer_targets"
RECURRING_CAMPAIGN_OPPS = "recurring_campaign_opportunities"


def confidence_for(count: int) -> float:
    return round(min(0.5 + 0.05 * count, 0.95), 3)


async def record_observation(
    session: AsyncSession,
    kind: str,
    key: str,
    extra: dict | None = None,
    increment: int = 1,
) -> Memory:
    """Upsert a memory entry, incrementing its observation count."""
    norm_key = " ".join(key.strip().lower().split())
    stmt = select(Memory).where(Memory.kind == kind, Memory.key == norm_key)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is None:
        entry = Memory(
            kind=kind,
            key=norm_key,
            value={"count": increment, **(extra or {})},
            confidence=confidence_for(increment),
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return entry
    count = int(existing.value.get("count", 0)) + increment
    merged = {**(existing.value), **(extra or {}), "count": count}
    existing.value = merged
    existing.confidence = confidence_for(count)
    await session.commit()
    await session.refresh(existing)
    return existing


async def observe_entities(session: AsyncSession, entities: dict) -> None:
    for club in entities.get("clubs", []):
        await record_observation(session, TRENDING_CLUBS, club)
    for person in entities.get("people", []):
        await record_observation(session, TRENDING_PLAYERS, person)
    for comp in entities.get("competitions", []):
        await record_observation(session, TRENDING_COMPETITIONS, comp)


async def observe_transfer(session: AsyncSession, player: str, to_club: str | None) -> None:
    await record_observation(
        session, TRENDING_PLAYERS, player, extra={"last_destination": to_club}
    )
    await record_observation(
        session,
        RECURRING_TRANSFER_TARGETS,
        f"{player} -> {to_club or 'unknown'}",
        extra={"player": player, "to_club": to_club},
    )


async def observe_campaign(session: AsyncSession, campaign_name: str, extra: dict | None = None) -> None:
    await record_observation(session, RECURRING_CAMPAIGN_OPPS, campaign_name, extra=extra)


# --- Phase 3 decision-memory kinds ---
HIGH_REACH_TOPICS = "high_reach_topics"
HIGH_ENGAGEMENT_TOPICS = "high_engagement_topics"
BEST_LEAGUES = "best_leagues"
BEST_TEAMS = "best_teams"
SUCCESSFUL_EXECUTIVE_DECISIONS = "successful_executive_decisions"


async def observe_opportunity_estimates(
    session: AsyncSession, topic: str, reach: int, engagement: float
) -> None:
    """Remember high-potential topics (thresholds keep memory signal-rich)."""
    if reach >= 15_000:
        await record_observation(
            session, HIGH_REACH_TOPICS, topic, extra={"reach": reach}
        )
    if engagement >= 0.04:
        await record_observation(
            session, HIGH_ENGAGEMENT_TOPICS, topic, extra={"engagement": engagement}
        )


async def observe_executive_decision(
    session: AsyncSession, topic: str, tier: str, score: float
) -> None:
    if tier in ("immediate", "create"):
        await record_observation(
            session,
            SUCCESSFUL_EXECUTIVE_DECISIONS,
            topic,
            extra={"tier": tier, "score": score},
        )


async def observe_graded_league_team(
    session: AsyncSession, league: str, teams: list[str], correct: bool
) -> None:
    """Track predictive strength by league/team (count only; accuracy derived)."""
    await record_observation(
        session, BEST_LEAGUES, league or "unknown", extra={"correct": correct}
    )
    for team in teams:
        await record_observation(
            session, BEST_TEAMS, team, extra={"correct": correct}
        )


# --- Phase 4 content-memory kinds ---
BEST_TITLES = "best_titles"
BEST_HOOKS = "best_hooks"
BEST_REGIONS = "best_regions"
BEST_PUBLISH_TIMES = "best_publish_times"
BEST_CONTENT_TYPES = "best_content_types"
HIGHEST_RPM_TOPICS = "highest_rpm_topics"


async def observe_script_quality(
    session: AsyncSession, title: str, hook: str, content_type: str,
    overall_score: float, approved: bool,
) -> None:
    """Remember high-quality titles/hooks/types (approved only)."""
    if not approved:
        return
    await record_observation(session, BEST_TITLES, title[:120], extra={"score": overall_score})
    await record_observation(session, BEST_HOOKS, hook[:160], extra={"score": overall_score})
    await record_observation(
        session, BEST_CONTENT_TYPES, content_type, extra={"score": overall_score}
    )


async def observe_region_performance(
    session: AsyncSession, region: str, monetization: float, publish_time: str,
    topic: str = "",
) -> None:
    """Remember monetizable regions + slots (bar: monetization ≥ 0.5)."""
    if monetization >= 0.5:
        await record_observation(
            session, BEST_REGIONS, region,
            extra={"monetization": monetization, "topic": topic},
        )
    await record_observation(
        session, BEST_PUBLISH_TIMES, publish_time, extra={"region": region}
    )


async def observe_rpm_topic(session: AsyncSession, topic: str, rpm: float) -> None:
    if rpm >= 4.0:
        await record_observation(session, HIGHEST_RPM_TOPICS, topic, extra={"rpm": rpm})


# --- Phase 5 video-production memory kinds ---
BEST_VIDEO_FORMATS = "best_video_formats"
BEST_VIDEO_STYLES = "best_video_styles"
BEST_VOICE_PROFILES = "best_voice_profiles"
BEST_PACING = "best_pacing"
BEST_SCENE_STRUCTURES = "best_scene_structures"
BEST_REGION_VARIANTS = "best_region_variants"
BEST_VISUAL_STYLES = "best_visual_styles"
HIGHEST_QUALITY_FORMATS = "highest_quality_formats"
PRODUCTION_FAILURES = "production_failures"
PROVIDER_RELIABILITY = "provider_reliability"


async def observe_approved_video(
    session: AsyncSession, content_type: str, style: str, pacing: str,
    voice_profile: str, scene_count: int, visual_style: str,
    overall_score: float, region: str | None = None,
) -> None:
    """Remember what good looks like — approved videos only."""
    await record_observation(session, BEST_VIDEO_FORMATS, content_type, extra={"score": overall_score})
    await record_observation(session, BEST_VIDEO_STYLES, style, extra={"score": overall_score})
    await record_observation(session, BEST_VOICE_PROFILES, voice_profile, extra={"score": overall_score})
    await record_observation(session, BEST_PACING, pacing, extra={"score": overall_score})
    await record_observation(
        session, BEST_SCENE_STRUCTURES, f"{scene_count}-scenes", extra={"score": overall_score})
    await record_observation(session, BEST_VISUAL_STYLES, visual_style, extra={"score": overall_score})
    await record_observation(
        session, HIGHEST_QUALITY_FORMATS, content_type, extra={"score": overall_score})
    if region:
        await record_observation(
            session, BEST_REGION_VARIANTS, region, extra={"score": overall_score})


async def observe_production_failure(
    session: AsyncSession, stage: str, provider: str, error: str,
) -> None:
    await record_observation(
        session, PRODUCTION_FAILURES, stage,
        extra={"provider": provider, "error": error[:200]},
    )
    await record_observation(
        session, PROVIDER_RELIABILITY, provider, extra={"failure": True, "stage": stage})


async def observe_provider_success(session: AsyncSession, provider: str, stage: str) -> None:
    await record_observation(
        session, PROVIDER_RELIABILITY, provider, extra={"failure": False, "stage": stage})
