"""Phase 1 tests: config, agent framework, retry, API, models."""
from __future__ import annotations

import pytest

from app.agents import get_agent_names, register_all_agents
from app.agents.base import AgentContext, AgentStatus
from app.agents.registry import registry
from app.core.config import Settings
from app.core.retry import run_with_retry
from app.db.base import Base
from app.db.models import (
    AgentRecord,
    Analytics,
    Club,
    Match,
    Memory,
    News,
    Player,
    Prediction,
    Publication,
    Script,
    Task,
    Transfer,
    Video,
)


def test_settings_defaults():
    s = Settings(environment="test", database_url="sqlite+aiosqlite:///:memory:")
    assert s.app_name == "FootballPulse V2"
    assert s.api_prefix == "/api/v1"


def test_all_models_registered():
    tables = set(Base.metadata.tables.keys())
    for expected in [
        "news", "matches", "clubs", "players", "transfers", "predictions",
        "videos", "scripts", "analytics", "memory", "agents", "tasks", "publications",
    ]:
        assert expected in tables, f"missing table {expected}"


def test_agent_roster_has_12():
    from app.agents import CANONICAL_PHASE1_AGENTS

    register_all_agents()
    # Phase 1 canonical roster intact; Phase 2 may add agents (e.g. campaign).
    for name in CANONICAL_PHASE1_AGENTS:
        assert name in registry.names(), f"missing canonical agent {name}"
    assert len(get_agent_names()) >= 12


@pytest.mark.asyncio
async def test_agent_run_succeeds():
    register_all_agents()
    agent = registry.get("learning")  # Phase-1 stub (untouched by Phases 2-4)
    result = await agent.run(AgentContext(payload={"foo": "bar"}))
    assert result.status == AgentStatus.SUCCEEDED
    assert "stub executed" in result.output["message"]


@pytest.mark.asyncio
async def test_agent_run_failure_captured():
    from app.agents.base import AgentMetadata, BaseAgent

    class Boom(BaseAgent):
        metadata = AgentMetadata(name="boom_test", description="boom")

        async def handle(self, ctx: AgentContext) -> dict:
            raise RuntimeError("kaboom")

    agent = Boom()
    result = await agent.run(AgentContext(), max_attempts=1)
    assert result.status == AgentStatus.FAILED
    assert result.error == "kaboom"


@pytest.mark.asyncio
async def test_retry_eventually_succeeds():
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("not yet")
        return "ok"

    out = await run_with_retry(flaky, max_attempts=3, base_delay=0.01)
    assert out == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_retry_exhaustion_reraises():
    async def always_fail() -> None:
        raise ValueError("bad")

    with pytest.raises(ValueError):
        await run_with_retry(always_fail, max_attempts=2, base_delay=0.01)


def test_api_app_builds():
    from fastapi.testclient import TestClient

    from app.main import create_app

    s = Settings(environment="test", database_url="sqlite+aiosqlite:///:memory:")
    app = create_app(s)
    client = TestClient(app)
    r = client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"
    r = client.get("/api/v1/agents")
    assert r.status_code == 200
    assert len(r.json()["agents"]) >= 12
