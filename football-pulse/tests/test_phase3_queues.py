"""Phase 3 tests: decision queues + worker processing (FakeRedis)."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.models import Prediction
from app.db.models.phase3 import ContentOpportunity, ExecutiveDecision
from app.queue import decision_queues
from app.queue import worker as worker_module

settings = Settings(environment="test", database_url="sqlite+aiosqlite:///:memory:")


def _fake_redis(monkeypatch):
    from fakeredis.aioredis import FakeRedis

    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(decision_queues, "get_redis", lambda *a, **k: fake)
    monkeypatch.setattr(worker_module, "dequeue_decision", decision_queues.dequeue_decision)
    return fake


def test_decision_queue_mapping_complete():
    assert set(decision_queues.QUEUE_TO_AGENT) == {
        "fp:queue:prediction", "fp:queue:executive", "fp:queue:opportunity",
    }
    assert decision_queues.queue_for_agent("prediction") == "fp:queue:prediction"
    assert decision_queues.queue_for_agent("executive") == "fp:queue:executive"
    assert decision_queues.queue_for_agent("content_opportunity") == "fp:queue:opportunity"
    assert decision_queues.queue_for_agent("nope") is None
    assert len(decision_queues.decision_queue_names()) == 3


async def test_enqueue_invalid_decision_queue_raises():
    with pytest.raises(ValueError):
        await decision_queues.enqueue_decision("fp:queue:nope", {}, settings)


async def test_enqueue_dequeue_roundtrip(monkeypatch):
    _fake_redis(monkeypatch)
    job_id = await decision_queues.enqueue_decision(
        "fp:queue:prediction", {"home_club": "A", "away_club": "B"}, settings)
    assert job_id
    assert await decision_queues.decision_queue_length("fp:queue:prediction", settings) == 1
    envelope = await decision_queues.dequeue_decision("fp:queue:prediction", settings, timeout=1)
    assert envelope["id"] == job_id
    assert envelope["agent"] == "prediction"


async def test_worker_processes_all_decision_queues_end_to_end(
    monkeypatch, session_factory, sample_prediction_request,
    sample_decision_candidate, sample_opportunity_items,
):
    _fake_redis(monkeypatch)
    from app.agents import register_all_agents

    register_all_agents()
    await decision_queues.enqueue_decision("fp:queue:prediction", sample_prediction_request, settings)
    await decision_queues.enqueue_decision("fp:queue:opportunity", {"items": sample_opportunity_items}, settings)
    await decision_queues.enqueue_decision("fp:queue:executive", sample_decision_candidate, settings)

    assert await worker_module.run_decision_queue_once("fp:queue:prediction") is True
    assert await worker_module.run_decision_queue_once("fp:queue:opportunity") is True
    assert await worker_module.run_decision_queue_once("fp:queue:executive") is True

    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(Prediction))).scalar() == 1
        assert (await session.execute(select(func.count()).select_from(ContentOpportunity))).scalar() == 2
        assert (await session.execute(select(func.count()).select_from(ExecutiveDecision))).scalar() == 1


async def test_worker_empty_decision_queue_returns_false(monkeypatch):
    _fake_redis(monkeypatch)
    assert await worker_module.run_decision_queue_once("fp:queue:executive") is False


def test_all_phase3_queues_distinct_from_phase2():
    from app.queue import intel_queues

    assert not set(decision_queues.QUEUE_TO_AGENT) & set(intel_queues.QUEUE_TO_AGENT)
    assert len(decision_queues.QUEUE_TO_AGENT) + len(intel_queues.QUEUE_TO_AGENT) == 7
