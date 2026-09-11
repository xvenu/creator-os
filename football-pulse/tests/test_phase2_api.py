"""Phase 2 tests: intelligence API endpoints (seeded via agents)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents.base import AgentContext
from app.api.deps import get_db
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def api_client(session_factory):
    settings = Settings(environment="test", database_url="sqlite+aiosqlite:///:memory:")
    app = create_app(settings)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


async def _seed(api_client, sample_articles, sample_match, sample_rumors, sample_campaigns) -> None:
    from app.agents.campaign_agent import CampaignIntelligenceAgent
    from app.agents.match_agent import MatchAnalysisAgent
    from app.agents.news_agent import NewsIntelligenceAgent
    from app.agents.transfer_agent import TransferIntelligenceAgent

    await NewsIntelligenceAgent().run(AgentContext(payload={"articles": sample_articles}))
    await MatchAnalysisAgent().run(AgentContext(payload=sample_match))
    await TransferIntelligenceAgent().run(AgentContext(payload={"rumors": sample_rumors}))
    await TransferIntelligenceAgent().run(AgentContext(payload={
        "player": "Jude Bellingham", "from_club": "Dortmund",
        "to_club": "Real Madrid", "sources": ["Official"], "status": "confirmed",
    }))
    await CampaignIntelligenceAgent().run(AgentContext(payload={"listings": sample_campaigns}))


async def test_news_endpoints(api_client, sample_articles, sample_match, sample_rumors, sample_campaigns):
    await _seed(api_client, sample_articles, sample_match, sample_rumors, sample_campaigns)
    r = api_client.get("/api/v1/news/")
    assert r.status_code == 200 and r.json()["count"] == 3
    r = api_client.get("/api/v1/news/top")
    assert r.status_code == 200 and r.json()["count"] == 3
    assert r.json()["items"][0]["breaking_news"] is True
    r = api_client.get("/api/v1/news/breaking")
    assert r.status_code == 200 and r.json()["count"] >= 1


async def test_match_endpoints(api_client, sample_articles, sample_match, sample_rumors, sample_campaigns):
    await _seed(api_client, sample_articles, sample_match, sample_rumors, sample_campaigns)
    r = api_client.get("/api/v1/matches/analysis")
    assert r.status_code == 200 and r.json()["count"] == 1
    analysis_id = r.json()["items"][0]["id"]
    r = api_client.get(f"/api/v1/matches/analysis/{analysis_id}")
    assert r.status_code == 200
    assert "Arsenal" in r.json()["narrative"]
    r = api_client.get("/api/v1/matches/analysis/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


async def test_transfer_endpoints(api_client, sample_articles, sample_match, sample_rumors, sample_campaigns):
    await _seed(api_client, sample_articles, sample_match, sample_rumors, sample_campaigns)
    r = api_client.get("/api/v1/transfers/")
    assert r.status_code == 200 and r.json()["count"] == 2
    r = api_client.get("/api/v1/transfers/top-rumors")
    assert r.status_code == 200
    assert all(i["status"] != "confirmed" for i in r.json()["items"])
    r = api_client.get("/api/v1/transfers/confirmed")
    assert r.status_code == 200 and r.json()["count"] == 1
    assert r.json()["items"][0]["player"] == "Jude Bellingham"


async def test_campaign_endpoints(api_client, sample_articles, sample_match, sample_rumors, sample_campaigns):
    await _seed(api_client, sample_articles, sample_match, sample_rumors, sample_campaigns)
    r = api_client.get("/api/v1/campaigns/")
    assert r.status_code == 200 and r.json()["count"] == 2
    r = api_client.get("/api/v1/campaigns/top")
    assert r.status_code == 200
    assert r.json()["items"][0]["campaign_name"] == "PremClip Pro"
    r = api_client.get("/api/v1/campaigns/active")
    assert r.status_code == 200 and r.json()["count"] == 2
