"""Phase 3 tests: predictions / opportunities / executive API endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents.base import AgentContext
from app.api.deps import get_db
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def decision_client(session_factory):
    settings = Settings(environment="test", database_url="sqlite+aiosqlite:///:memory:")
    app = create_app(settings)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


async def _seed(decision_client, sample_prediction_request, sample_decision_candidate,
                sample_opportunity_items) -> None:
    from app.agents.executive_agent import ExecutiveAgent
    from app.agents.opportunity_agent import ContentOpportunityAgent
    from app.agents.prediction_agent import PredictionAgent

    made = await PredictionAgent().run(AgentContext(payload=sample_prediction_request))
    pred_id = made.output["items"][0]["prediction_id"]
    await PredictionAgent().run(AgentContext(payload={
        "results": [{"prediction_id": pred_id, "home_score": 2, "away_score": 1}]
    }))
    await PredictionAgent().run(AgentContext(payload={
        "home_club": "Real Madrid", "away_club": "Girona", "league": "La Liga",
        "home_form": {"last_results": ["W", "W", "W"]}, "away_form": {"last_results": ["L", "L"]},
    }))
    await ContentOpportunityAgent().run(AgentContext(payload={"items": sample_opportunity_items}))
    await ExecutiveAgent().run(AgentContext(payload=sample_decision_candidate))


async def test_prediction_endpoints(decision_client, sample_prediction_request,
                                    sample_decision_candidate, sample_opportunity_items):
    await _seed(decision_client, sample_prediction_request, sample_decision_candidate,
                sample_opportunity_items)
    r = decision_client.get("/api/v1/predictions/")
    assert r.status_code == 200 and r.json()["count"] == 2
    r = decision_client.get("/api/v1/predictions/top")
    assert r.status_code == 200
    # One graded → only the pending La Liga prediction is "top".
    assert r.json()["count"] == 1
    r = decision_client.get("/api/v1/predictions/metrics")
    assert r.status_code == 200
    scopes = {m["scope"]: m for m in r.json()["scopes"]}
    assert scopes["overall"]["total"] == 1
    assert scopes["overall"]["accuracy"] == 1.0  # 2-1 predicted, 2-1 actual
    assert "league:Premier League" in scopes


async def test_opportunity_endpoints(decision_client, sample_prediction_request,
                                     sample_decision_candidate, sample_opportunity_items):
    await _seed(decision_client, sample_prediction_request, sample_decision_candidate,
                sample_opportunity_items)
    r = decision_client.get("/api/v1/opportunities/")
    assert r.status_code == 200 and r.json()["count"] == 2
    r = decision_client.get("/api/v1/opportunities/top")
    assert r.status_code == 200
    assert r.json()["items"][0]["topic"] == "Osimhen transfer"
    r = decision_client.get("/api/v1/opportunities/high-priority")
    assert r.status_code == 200
    assert all(i["urgency"] in ("critical", "high") for i in r.json()["items"])


async def test_executive_endpoints(decision_client, sample_prediction_request,
                                   sample_decision_candidate, sample_opportunity_items):
    await _seed(decision_client, sample_prediction_request, sample_decision_candidate,
                sample_opportunity_items)
    r = decision_client.get("/api/v1/executive/decisions")
    assert r.status_code == 200 and r.json()["count"] == 1
    item = r.json()["items"][0]
    assert item["recommendation"]["should_create_content"] is True
    assert len(item["task_ids"]) == 1
    r = decision_client.get("/api/v1/executive/summary")
    assert r.status_code == 200
    summary = r.json()
    assert summary["total_decisions"] == 1
    assert summary["total_tasks"] == 1
    assert summary["total_opportunities"] == 2
    assert summary["opportunity_conversion_rate"] == 0.5
