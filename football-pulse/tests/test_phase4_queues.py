"""Phase 4 tests: content queues + worker processing (FakeRedis)."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.models import Script, Task
from app.db.models.phase4 import ContentPackage, ResearchBrief
from app.queue import content_queues
from app.queue import worker as worker_module

settings = Settings(environment="test", database_url="sqlite+aiosqlite:///:memory:")


def _fake_redis(monkeypatch):
    from fakeredis.aioredis import FakeRedis

    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(content_queues, "get_redis", lambda *a, **k: fake)
    monkeypatch.setattr(worker_module, "dequeue_content", content_queues.dequeue_content)
    return fake


def test_content_queue_mapping_complete():
    assert set(content_queues.QUEUE_TO_AGENT) == {
        "fp:queue:research", "fp:queue:planner", "fp:queue:script",
        "fp:queue:seo", "fp:queue:thumbnail", "fp:queue:region", "fp:queue:packaging",
    }
    assert content_queues.queue_for_agent("research") == "fp:queue:research"
    assert content_queues.queue_for_agent("script_writer") == "fp:queue:script"
    assert content_queues.queue_for_agent("packaging") == "fp:queue:packaging"
    assert content_queues.queue_for_agent("nope") is None
    assert len(content_queues.content_queue_names()) == 7


async def test_enqueue_invalid_content_queue_raises():
    with pytest.raises(ValueError):
        await content_queues.enqueue_content("fp:queue:nope", {}, settings)


async def test_enqueue_dequeue_roundtrip(monkeypatch):
    _fake_redis(monkeypatch)
    job_id = await content_queues.enqueue_content("fp:queue:seo", {"topic": "T"}, settings)
    assert job_id
    assert await content_queues.content_queue_length("fp:queue:seo", settings) == 1
    envelope = await content_queues.dequeue_content("fp:queue:seo", settings, timeout=1)
    assert envelope["id"] == job_id
    assert envelope["agent"] == "seo"


async def test_worker_processes_content_queues_end_to_end(
    monkeypatch, session_factory, sample_intel_items, sample_brief,
):
    _fake_redis(monkeypatch)
    from app.agents import register_all_agents

    register_all_agents()
    await content_queues.enqueue_content("fp:queue:research", {
        "topic": sample_brief["topic"], "items": sample_intel_items}, settings)
    await content_queues.enqueue_content("fp:queue:script", {
        "brief": sample_brief, "content_format": "transfer_update",
        "emit_task": {"agent": "seo", "kind": "generate_seo"}}, settings)

    assert await worker_module.run_content_queue_once("fp:queue:research") is True
    assert await worker_module.run_content_queue_once("fp:queue:script") is True

    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(ResearchBrief))).scalar() == 1
        assert (await session.execute(select(func.count()).select_from(Script))).scalar() == 1
        # Script agent emitted the next-stage SEO task.
        tasks = (await session.execute(select(Task))).scalars().all()
        assert len(tasks) == 1
        assert tasks[0].agent_name == "seo" and tasks[0].payload["source"] == "script_writer"


async def test_worker_empty_content_queue_returns_false(monkeypatch):
    _fake_redis(monkeypatch)
    assert await worker_module.run_content_queue_once("fp:queue:packaging") is False


async def test_all_queue_names_distinct():
    from app.queue import decision_queues, intel_queues

    all_names = (set(content_queues.QUEUE_TO_AGENT)
                 | set(decision_queues.QUEUE_TO_AGENT)
                 | set(intel_queues.QUEUE_TO_AGENT))
    assert len(all_names) == 14


async def test_invalid_emit_spec_creates_no_task(monkeypatch, session_factory, sample_brief):
    _fake_redis(monkeypatch)
    from app.agents import register_all_agents

    register_all_agents()
    await content_queues.enqueue_content("fp:queue:script", {
        "brief": sample_brief, "emit_task": {"agent": "", "kind": ""}}, settings)
    assert await worker_module.run_content_queue_once("fp:queue:script") is True
    async with session_factory() as session:
        from app.db.models import Task
        from sqlalchemy import func, select
        assert (await session.execute(select(func.count()).select_from(Task))).scalar() == 0
