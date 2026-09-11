"""Phase 4 tests: packaging service + Packaging Agent (full assembly)."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentStatus
from app.db.models.phase4 import ContentPackage, PublishingStrategy
from app.services import packaging_service as svc


def _parts(overall: float = 0.85) -> dict:
    return {
        "topic": "Arsenal record signing",
        "content_type": "transfer_update",
        "script": {"title": "T", "hook": "H", "body": "B"},
        "seo": {"title_options": ["T"]},
        "thumbnail": {"thumbnail_text": "DONE DEAL"},
        "regions": [{"region": "UK"}, {"region": "US"}],
        "quality": {"overall_score": overall},
        "opportunity_score": 0.8,
        "platform_targets": ["youtube", "tiktok"],
    }


def test_assemble_package_status_gate():
    assert svc.assemble_package(_parts(0.85))["status"] == "assembled"
    assert svc.assemble_package(_parts(0.5))["status"] == "needs_review"


def test_assemble_package_rejects_missing_parts():
    with pytest.raises(ValueError):
        svc.assemble_package({"topic": "T"})


def test_publishing_strategy_revenue_and_schedule():
    package = svc.assemble_package(_parts())
    strategy = svc.build_publishing_strategy(
        {"platform_targets": ["youtube", "tiktok"]}, package["opportunity_score"])
    assert strategy["revenue_opportunity_score"] > 0
    assert len(strategy["best_regions"]) == 3
    assert len(strategy["platform_schedule"]) == 2
    assert strategy["best_language"] and strategy["best_publish_time"]


async def test_packaging_agent_end_to_end(session_factory):
    from app.agents.packaging_agent import PackagingAgent

    result = await PackagingAgent().run(AgentContext(payload=_parts()))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["packaged"] == 1
    item = result.output["items"][0]
    for key in ("content_package_id", "script", "seo", "thumbnail_strategy",
                "target_regions", "publishing_strategy"):
        assert key in item, f"missing {key}"
    assert item["status"] == "assembled"

    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(ContentPackage))).scalar() == 1
        assert (await session.execute(select(func.count()).select_from(PublishingStrategy))).scalar() == 1


async def test_full_pipeline_chain(session_factory, sample_brief):
    """Brief → script → SEO → thumbnail → package: the Phase 4 spine."""
    from app.agents.packaging_agent import PackagingAgent
    from app.agents.script_agent import ScriptWriterAgent
    from app.agents.seo_agent import SEOAgent
    from app.agents.thumbnail_agent import ThumbnailStrategyAgent

    script_out = await ScriptWriterAgent().run(AgentContext(payload={
        "brief": sample_brief, "content_format": "transfer_update", "length": "60s"}))
    script_item = script_out.output["items"][0]
    seo_out = await SEOAgent().run(AgentContext(payload={
        "topic": sample_brief["topic"], "script_id": script_item["script_id"]}))
    thumb_out = await ThumbnailStrategyAgent().run(AgentContext(payload={
        "topic": sample_brief["topic"], "content_format": "transfer_update",
        "script_id": script_item["script_id"]}))
    package_out = await PackagingAgent().run(AgentContext(payload={
        "topic": sample_brief["topic"], "content_type": "transfer_update",
        "script": script_item, "seo": seo_out.output["items"][0],
        "thumbnail": thumb_out.output["items"][0],
        "regions": [{"region": "UK"}, {"region": "US"}],
        "quality": script_item["quality"], "opportunity_score": 0.8,
        "script_id": script_item["script_id"],
        "seo_id": seo_out.output["items"][0]["seo_id"],
        "thumbnail_id": thumb_out.output["items"][0]["thumbnail_id"],
    }))
    assert package_out.output["packaged"] == 1
    assert package_out.output["items"][0]["status"] in ("assembled", "needs_review")


async def test_package_embeds_asset_ids(session_factory):
    from app.agents.packaging_agent import PackagingAgent

    job = _parts()
    job.update({"brief_id": "11111111-1111-1111-1111-111111111111",
                "script_id": "22222222-2222-2222-2222-222222222222"})
    result = await PackagingAgent().run(AgentContext(payload=job))
    assert result.status == AgentStatus.SUCCEEDED
    async with session_factory() as session:
        from app.db.models.phase4 import ContentPackage
        from sqlalchemy import select
        row = (await session.execute(select(ContentPackage))).scalar_one()
        assert str(row.brief_id) == "11111111-1111-1111-1111-111111111111"
        assert str(row.script_id) == "22222222-2222-2222-2222-222222222222"


async def test_needs_review_path(session_factory):
    from app.agents.packaging_agent import PackagingAgent

    result = await PackagingAgent().run(AgentContext(payload=_parts(overall=0.4)))
    assert result.output["items"][0]["status"] == "needs_review"
