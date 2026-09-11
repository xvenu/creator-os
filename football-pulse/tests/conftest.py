"""Phase 2 test fixtures: isolated in-memory SQLite per test + agent wiring."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
import app.db.models  # noqa: F401
import app.db.models.phase2  # noqa: F401
import app.db.models.phase3  # noqa: F401
import app.db.models.phase4  # noqa: F401
import app.db.models.phase5  # noqa: F401


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    from app.agents import (
        campaign_agent,
        executive_agent,
        match_agent,
        news_agent,
        opportunity_agent,
        packaging_agent,
        planner_agent,
        prediction_agent,
        region_agent,
        research_agent,
        script_agent,
        seo_agent,
        thumbnail_agent,
        transfer_agent,
    )
    from app.modules.zoza_client import agent as zoza_agent_mod

    mods = (
        news_agent, match_agent, transfer_agent, campaign_agent,
        prediction_agent, executive_agent, opportunity_agent,
        research_agent, planner_agent, script_agent, seo_agent,
        thumbnail_agent, region_agent, packaging_agent,
        zoza_agent_mod,
    )
    for mod in mods:
        mod.set_session_factory(factory)
    yield factory
    for mod in mods:
        mod.set_session_factory(None)
    await engine.dispose()


@pytest.fixture
def sample_articles() -> list[dict]:
    return [
        {
            "title": "Arsenal confirm record signing of striker in official statement",
            "source": "BBC Sport",
            "url": "https://example.com/arsenal-signing",
            "body": "Arsenal have confirmed the record signing of a new striker. The deal was completed on deadline day.",
        },
        {
            "title": "Arsenal announce record striker signing, club confirms",
            "source": "Sky Sports",
            "url": "https://example.com/arsenal-signing-2",
            "body": "Arsenal announced a record deal for a striker as the Champions League race heats up.",
        },
        {
            "title": "Local weather delays Sunday league kickoff times",
            "source": "Unknown Blog",
            "url": "https://example.com/weather",
            "body": "Rain is expected across the region this weekend.",
        },
    ]


@pytest.fixture
def sample_match() -> dict:
    return {
        "home_club": "Arsenal",
        "away_club": "Chelsea",
        "league": "Premier League",
        "status": "completed",
        "home_score": 2,
        "away_score": 0,
        "events": [
            {"type": "goal", "player": "Bukayo Saka", "team": "home", "minute": 23},
            {"type": "assist", "player": "Martin Odegaard", "team": "home", "minute": 23},
            {"type": "goal", "player": "Kai Havertz", "team": "home", "minute": 81},
            {"type": "yellow", "player": "Enzo Fernandez", "team": "away", "minute": 55},
            {"type": "clean_sheet", "player": "David Raya", "team": "home", "minute": 90},
        ],
        "home_form": {"club": "Arsenal", "last_results": ["W", "W", "D", "W", "W"], "goals_for": 11, "goals_against": 3},
        "away_form": {"club": "Chelsea", "last_results": ["L", "D", "L", "W", "L"], "goals_for": 4, "goals_against": 9},
    }


@pytest.fixture
def sample_rumors() -> list[dict]:
    return [
        {
            "player": "Victor Osimhen",
            "from_club": "Napoli",
            "to_club": "Arsenal",
            "sources": ["David Ornstein", "BBC Sport"],
            "status": "talks",
        },
        {
            "player": "Victor Osimhen",
            "from_club": "Napoli",
            "to_club": "Arsenal",
            "sources": ["Sky Sports"],
            "status": "talks",
        },
    ]


@pytest.fixture
def sample_campaigns() -> list[dict]:
    return [
        {
            "campaign_name": "PremClip Pro",
            "platform": "TikTok",
            "payout_model": "fixed",
            "payout_estimate": 800.0,
            "requirements": {"min_followers": 1000},
            "niche": "football",
            "active": True,
            "countries": ["global"],
        },
        {
            "campaign_name": "ViralGaming Clips",
            "platform": "YouTube",
            "payout_model": "unknown",
            "payout_estimate": 50.0,
            "requirements": {"min_followers": 50000, "exclusivity": True, "upfront_fee": True},
            "niche": "gaming",
            "active": True,
            "countries": ["US"],
        },
    ]


@pytest.fixture
def sample_prediction_request() -> dict:
    return {
        "home_club": "Arsenal",
        "away_club": "Chelsea",
        "league": "Premier League",
        "home_form": {"club": "Arsenal", "last_results": ["W", "W", "D", "W", "W"], "goals_for": 11, "goals_against": 3},
        "away_form": {"club": "Chelsea", "last_results": ["L", "D", "L", "W", "L"], "goals_for": 4, "goals_against": 9},
        "h2h": ["H", "H", "D", "H"],
    }


@pytest.fixture
def sample_decision_candidate() -> dict:
    return {
        "title": "Arsenal vs Chelsea Prediction",
        "topic": "Arsenal vs Chelsea",
        "source_kind": "prediction",
        "signals": {
            "news_importance": 0.85,
            "transfer_credibility": 0.5,
            "prediction_confidence": 0.8,
            "campaign_roi": 0.7,
            "trend_score": 0.9,
        },
    }


@pytest.fixture
def sample_opportunity_items() -> list[dict]:
    return [
        {
            "title": "Osimhen to Arsenal: Done Deal?",
            "topic": "Osimhen transfer",
            "source_kind": "transfer",
            "signals": {"transfer_credibility": 0.9, "trend_score": 0.8},
            "meta": {"breaking": True},
        },
        {
            "title": "Sunday League Roundup",
            "topic": "grassroots",
            "source_kind": "news",
            "signals": {"news_importance": 0.2, "trend_score": 0.1},
        },
    ]


@pytest.fixture
def sample_intel_items() -> list[dict]:
    return [
        {
            "title": "Arsenal confirm record striker signing",
            "source_kind": "news",
            "facts": [
                {"text": "Arsenal confirmed a record signing.", "confidence": 0.9, "source": "news"},
                {"text": "The deal was completed on deadline day.", "confidence": 0.8, "source": "news"},
            ],
            "entities": {"clubs": ["arsenal"], "competitions": ["premier league"], "people": ["Mikel Arteta"]},
            "published_at": "2026-09-01T10:00:00+00:00",
        },
        {
            "title": "Arsenal announce record deal",
            "source_kind": "news",
            "facts": [
                {"text": "Arsenal confirmed a record signing.", "confidence": 0.7, "source": "news"},
                {"text": "Fans celebrated outside the stadium.", "confidence": 0.6, "source": "news"},
            ],
            "entities": {"clubs": ["arsenal"], "competitions": [], "people": []},
            "published_at": "2026-09-01T12:00:00+00:00",
        },
    ]


@pytest.fixture
def sample_brief() -> dict:
    return {
        "topic": "Arsenal record signing",
        "facts": [
            {"text": "Arsenal confirmed a record signing.", "confidence": 0.9},
            {"text": "The deal was completed on deadline day.", "confidence": 0.8},
            {"text": "Fans celebrated outside the stadium.", "confidence": 0.6},
        ],
        "supporting_points": ["Key angle: arsenal drive the narrative."],
        "entities": {"clubs": ["arsenal"], "competitions": ["premier league"], "people": []},
    }


@pytest.fixture
def sample_content_package() -> dict:
    """Phase 4-style content package ready for Zoza dispatch."""
    return {
        "package_id": "11111111-1111-1111-1111-111111111111",
        "topic": "Arsenal record signing",
        "title": "Arsenal Record Signing — Transfer Update",
        "summary": "Arsenal confirmed a record signing on deadline day.",
        "content_type": "transfer_update",
        "script": {
            "hook": "It's happening.",
            "body": "Arsenal confirmed a record signing on deadline day.",
            "outro": "Subscribe for updates.",
        },
        "seo": {"title_options": ["Arsenal Record Signing"], "hashtags": ["#football", "#arsenal"]},
        "thumbnail": {"thumbnail_text": "DONE DEAL"},
        "regions": ["UK", "US"],
        "quality": {"overall_score": 0.85},
        "opportunity_score": 0.8,
        "platform_targets": ["youtube", "tiktok"],
    }
