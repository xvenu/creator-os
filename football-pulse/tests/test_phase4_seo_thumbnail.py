"""Phase 4 tests: SEO + thumbnail services and agents."""
from __future__ import annotations

from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentStatus
from app.db.models.phase4 import SEOAsset, ThumbnailStrategy
from app.services import seo_service as seo
from app.services import thumbnail_service as thumb


def test_extract_keywords_prioritizes_topic():
    kws = seo.extract_keywords("Arsenal Striker Signing", "Arsenal confirmed a record deal")
    assert "arsenal" in kws[:3]


def test_generate_seo_output_shape():
    out = seo.generate_seo("Arsenal Striker Signing", "Record deal confirmed.", "Arsenal confirmed it.")
    assert len(out["title_options"]) >= 3
    assert len(out["description"]) >= 100
    assert out["hashtags"][0] == "#football"
    assert 0.0 <= out["seo_score"] <= 1.0
    assert out["keywords"]


def test_seo_score_rewards_good_assets():
    good = seo.score_seo(
        ["Arsenal Striker Signing Explained in Full Detail Here"], "x" * 150,
        ["arsenal", "striker", "signing", "deal", "news"], ["#football", "#arsenal", "#news"])
    bad = seo.score_seo(["Hi"], "short", ["a"], ["#x"] * 10)
    assert good > bad


def test_thumbnail_concept_shape():
    concept = thumb.generate_thumbnail("Arsenal Win Derby", "match_review",
                                       {"clubs": ["arsenal"]}, "high")
    assert len(concept["thumbnail_text"].split()) <= 5
    assert concept["emotional_trigger"] == "triumph"
    assert concept["color_strategy"]["background"]
    assert len(concept["visual_elements"]) >= 2
    assert 0.0 <= concept["click_probability"] <= 1.0


def test_thumbnail_trigger_by_format():
    assert thumb.generate_thumbnail("T", "breaking_news")["emotional_trigger"] == "urgency"
    assert thumb.generate_thumbnail("T", "transfer_update")["emotional_trigger"] == "shock"


async def test_seo_agent_persists(session_factory):
    from app.agents.seo_agent import SEOAgent

    result = await SEOAgent().run(AgentContext(payload={
        "topic": "Arsenal Striker Signing", "summary": "Record deal confirmed."}))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["generated"] == 1
    assert result.output["items"][0]["seo_id"]
    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(SEOAsset))).scalar() == 1


async def test_thumbnail_agent_persists(session_factory):
    from app.agents.thumbnail_agent import ThumbnailStrategyAgent

    result = await ThumbnailStrategyAgent().run(AgentContext(payload={
        "topic": "Arsenal Win Derby", "content_format": "match_review",
        "entities": {"clubs": ["arsenal"]}, "urgency": "high"}))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["generated"] == 1
    item = result.output["items"][0]
    assert item["thumbnail_id"] and item["click_probability"] > 0
    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(ThumbnailStrategy))).scalar() == 1


def test_hashtags_capped_and_prefixed():
    tags = seo.generate_hashtags(["arsenal", "striker", "signing", "deal", "news",
                                  "premier", "league", "record", "transfer", "club", "extra"])
    assert len(tags) == 8
    assert all(t.startswith("#") for t in tags)


def test_description_carries_cta_and_keywords():
    out = seo.generate_seo("Arsenal Striker Signing", "Record deal confirmed.")
    assert "Subscribe" in out["description"]
    assert "Keywords:" in out["description"]
