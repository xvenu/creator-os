"""Phase 3 tests: opportunity engine + Content Opportunity Agent."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentStatus
from app.db.models import Memory
from app.db.models.phase3 import ContentOpportunity
from app.services import opportunity_service as svc


def test_create_opportunity_defaults_and_validation():
    opp = svc.create_opportunity({"title": "Derby Preview", "topic": "derby", "source_kind": "match"})
    assert opp["content_type"] == "match_preview"
    with pytest.raises(ValueError):
        svc.create_opportunity({"title": "", "topic": "x"})
    with pytest.raises(ValueError):
        svc.create_opportunity({"title": "T", "source_kind": "gossip"})
    with pytest.raises(ValueError):
        svc.create_opportunity({"title": "T", "source_kind": "news", "content_type": "opera"})


def test_default_content_types():
    assert svc.create_opportunity(
        {"title": "T", "source_kind": "match", "status": "completed"})["content_type"] == "match_review"
    assert svc.create_opportunity(
        {"title": "T", "source_kind": "transfer"})["content_type"] == "transfer_update"
    assert svc.create_opportunity(
        {"title": "T", "source_kind": "campaign"})["content_type"] == "short"


def test_score_bounded_and_breaking_boosts():
    base = svc.score_opportunity(svc.create_opportunity({
        "title": "T", "source_kind": "news", "signals": {"news_importance": 0.5}}))
    breaking = svc.score_opportunity(svc.create_opportunity({
        "title": "T", "source_kind": "news", "signals": {"news_importance": 0.5},
        "meta": {"breaking": True}}))
    assert 0.0 <= base["score"] <= 1.0
    assert breaking["score"] > base["score"]
    assert breaking["urgency"] in ("low", "medium", "high", "critical")


def test_urgency_mapping():
    assert svc.score_opportunity({"title": "t", "topic": "t", "source_kind": "transfer",
                                  "signals": {"a": 1.0, "b": 1.0}, "meta": {"breaking": True}})["urgency"] == "critical"


def test_rank_orders_descending(sample_opportunity_items):
    ranked = svc.rank_opportunities([svc.create_opportunity(i) for i in sample_opportunity_items])
    assert ranked[0]["topic"] == "Osimhen transfer"
    assert ranked[0]["score"] >= ranked[1]["score"]


def test_estimate_value_positive_and_scaled():
    big = svc.estimate_value(0.9, "critical", ["youtube", "tiktok"])
    small = svc.estimate_value(0.2, "low", ["x"])
    assert big["estimated_reach"] > small["estimated_reach"] > 0
    assert big["estimated_value"] > small["estimated_value"] > 0


async def test_opportunity_agent_persists_and_ranks(session_factory, sample_opportunity_items):
    from app.agents.opportunity_agent import ContentOpportunityAgent

    agent = ContentOpportunityAgent()
    result = await agent.run(AgentContext(payload={"items": sample_opportunity_items}))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["created"] == 2
    first = result.output["items"][0]
    assert first["topic"] == "Osimhen transfer"
    for key in ("title", "topic", "score", "urgency", "content_type",
                "target_platforms", "estimated_reach", "estimated_value"):
        assert key in first, f"missing {key}"

    async with session_factory() as session:
        count = (await session.execute(select(func.count()).select_from(ContentOpportunity))).scalar()
        assert count == 2


async def test_high_reach_topic_memorized(session_factory, sample_opportunity_items):
    from app.agents.opportunity_agent import ContentOpportunityAgent

    await ContentOpportunityAgent().run(AgentContext(payload={"items": sample_opportunity_items}))
    async with session_factory() as session:
        mem = (await session.execute(
            select(Memory).where(Memory.kind == "high_reach_topics")
        )).scalars().all()
        assert len(mem) == 1
        assert "osimhen" in mem[0].key
