"""Phase 4 tests: content API endpoints (seeded via agents)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents.base import AgentContext
from app.api.deps import get_db
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def content_client(session_factory):
    settings = Settings(environment="test", database_url="sqlite+aiosqlite:///:memory:")
    app = create_app(settings)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


async def _seed(content_client, sample_intel_items, sample_brief) -> str:
    from app.agents.packaging_agent import PackagingAgent
    from app.agents.region_agent import RegionIntelligenceAgent
    from app.agents.research_agent import ResearchAgent
    from app.agents.script_agent import ScriptWriterAgent
    from app.agents.seo_agent import SEOAgent
    from app.agents.thumbnail_agent import ThumbnailStrategyAgent

    await ResearchAgent().run(AgentContext(payload={
        "topic": sample_brief["topic"], "items": sample_intel_items}))
    script_out = await ScriptWriterAgent().run(AgentContext(payload={
        "brief": sample_brief, "content_format": "transfer_update", "length": "60s"}))
    script_item = script_out.output["items"][0]
    seo_out = await SEOAgent().run(AgentContext(payload={
        "topic": sample_brief["topic"], "script_id": script_item["script_id"]}))
    thumb_out = await ThumbnailStrategyAgent().run(AgentContext(payload={
        "topic": sample_brief["topic"], "content_format": "transfer_update",
        "script_id": script_item["script_id"]}))
    await RegionIntelligenceAgent().run(AgentContext(payload={
        "topic": sample_brief["topic"], "limit": 5}))
    package_out = await PackagingAgent().run(AgentContext(payload={
        "topic": sample_brief["topic"], "content_type": "transfer_update",
        "script": script_item, "seo": seo_out.output["items"][0],
        "thumbnail": thumb_out.output["items"][0],
        "regions": [{"region": "UK"}], "quality": script_item["quality"],
        "opportunity_score": 0.8}))
    return package_out.output["items"][0]["content_package_id"]


async def test_research_and_script_endpoints(content_client, sample_intel_items, sample_brief):
    package_id = await _seed(content_client, sample_intel_items, sample_brief)
    r = content_client.get("/api/v1/research/")
    assert r.status_code == 200 and r.json()["count"] == 1
    r = content_client.get("/api/v1/research/by-topic", params={"topic": sample_brief["topic"]})
    assert r.status_code == 200 and r.json()["count"] == 1
    assert r.json()["items"][0]["facts"]
    r = content_client.get("/api/v1/scripts/")
    assert r.status_code == 200 and r.json()["count"] == 1
    r = content_client.get("/api/v1/scripts/approved")
    assert r.status_code == 200
    assert r.json()["count"] in (0, 1)


async def test_seo_thumbnail_region_endpoints(content_client, sample_intel_items, sample_brief):
    await _seed(content_client, sample_intel_items, sample_brief)
    r = content_client.get("/api/v1/seo/")
    assert r.status_code == 200 and r.json()["count"] == 1
    r = content_client.get("/api/v1/seo/top")
    assert r.status_code == 200 and r.json()["items"][0]["seo_score"] >= 0
    r = content_client.get("/api/v1/thumbnails/")
    assert r.status_code == 200 and r.json()["count"] == 1
    r = content_client.get("/api/v1/thumbnails/top")
    assert r.status_code == 200
    r = content_client.get("/api/v1/regions/")
    assert r.status_code == 200 and r.json()["count"] == 5
    r = content_client.get("/api/v1/regions/top")
    assert r.status_code == 200
    r = content_client.get("/api/v1/regions/by-tier/1")
    assert r.status_code == 200 and all(True for _ in r.json()["items"])


async def test_package_endpoints(content_client, sample_intel_items, sample_brief):
    package_id = await _seed(content_client, sample_intel_items, sample_brief)
    r = content_client.get("/api/v1/packages/")
    assert r.status_code == 200 and r.json()["count"] == 1
    r = content_client.get("/api/v1/packages/ready")
    assert r.status_code == 200
    r = content_client.get(f"/api/v1/packages/{package_id}")
    assert r.status_code == 200
    body = r.json()
    assert len(body["publishing_strategies"]) == 1
    assert body["publishing_strategies"][0]["revenue_opportunity_score"] > 0
    r = content_client.get("/api/v1/packages/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
