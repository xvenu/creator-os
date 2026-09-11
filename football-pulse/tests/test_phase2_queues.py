"""Phase 2 tests: intelligence queues + worker processing (FakeRedis)."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.models import News
from app.queue import intel_queues
from app.queue import worker as worker_module

settings = Settings(environment="test", database_url="sqlite+aiosqlite:///:memory:")


def _fake_redis(monkeypatch):
    from fakeredis.aioredis import FakeRedis

    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(intel_queues, "get_redis", lambda *a, **k: fake)
    monkeypatch.setattr(worker_module, "dequeue_intel", intel_queues.dequeue_intel)
    return fake


def test_intel_queue_mapping_complete():
    assert set(intel_queues.QUEUE_TO_AGENT) == {
        "fp:queue:news", "fp:queue:match_analysis", "fp:queue:transfer", "fp:queue:campaign",
    }
    assert intel_queues.queue_for_agent("news_intelligence") == "fp:queue:news"
    assert intel_queues.queue_for_agent("campaign_intelligence") == "fp:queue:campaign"
    assert intel_queues.queue_for_agent("nope") is None
    assert len(intel_queues.intel_queue_names()) == 4


async def test_enqueue_invalid_queue_raises():
    with pytest.raises(ValueError):
        await intel_queues.enqueue_intel("fp:queue:nope", {}, settings)


async def test_enqueue_dequeue_roundtrip(monkeypatch):
    _fake_redis(monkeypatch)
    job_id = await intel_queues.enqueue_intel("fp:queue:news", {"articles": []}, settings)
    assert job_id
    assert await intel_queues.intel_queue_length("fp:queue:news", settings) == 1
    envelope = await intel_queues.dequeue_intel("fp:queue:news", settings, timeout=1)
    assert envelope["id"] == job_id
    assert envelope["agent"] == "news_intelligence"


async def test_worker_processes_intel_queue_end_to_end(monkeypatch, session_factory, sample_articles):
    _fake_redis(monkeypatch)
    from app.agents import register_all_agents

    register_all_agents()
    await intel_queues.enqueue_intel("fp:queue:news", {"articles": sample_articles}, settings)
    worked = await worker_module.run_intel_queue_once("fp:queue:news")
    assert worked is True

    async with session_factory() as session:
        count = (await session.execute(select(func.count()).select_from(News))).scalar()
        assert count == 3


async def test_worker_empty_queue_returns_false(monkeypatch):
    _fake_redis(monkeypatch)
    assert await worker_module.run_intel_queue_once("fp:queue:transfer") is False
