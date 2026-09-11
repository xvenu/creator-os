"""Zoza refactor tests: fp:queue:zoza + worker dispatch (FakeRedis)."""
from __future__ import annotations

import pytest

from app.core.config import Settings
from app.queue import worker as worker_module
from app.queue import zoza_queues

settings = Settings(environment="test", database_url="sqlite+aiosqlite:///:memory:")


def _fake_redis(monkeypatch):
    from fakeredis.aioredis import FakeRedis

    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(zoza_queues, "get_redis", lambda *a, **k: fake)
    monkeypatch.setattr(worker_module, "dequeue_zoza", zoza_queues.dequeue_zoza)
    return fake


def test_zoza_queue_mapping():
    assert zoza_queues.zoza_queue_names() == ["fp:queue:zoza"]
    assert zoza_queues.queue_for_agent("zoza_dispatcher") == "fp:queue:zoza"
    assert zoza_queues.queue_for_agent("render") is None  # local render gone


async def test_enqueue_invalid_zoza_queue_raises():
    with pytest.raises(ValueError):
        await zoza_queues.enqueue_zoza({}, settings, queue_name="fp:queue:nope")


async def test_enqueue_dequeue_roundtrip(monkeypatch):
    _fake_redis(monkeypatch)
    job_id = await zoza_queues.enqueue_zoza({"package": {"title": "T"}}, settings)
    assert job_id
    assert await zoza_queues.zoza_queue_length("fp:queue:zoza", settings) == 1
    envelope = await zoza_queues.dequeue_zoza("fp:queue:zoza", settings, timeout=1)
    assert envelope["agent"] == "zoza_dispatcher"


async def test_worker_dispatches_package_to_factory(
    monkeypatch, session_factory, tmp_path, sample_content_package,
):
    _fake_redis(monkeypatch)
    jobs = tmp_path / "zoza" / "jobs"
    jobs.mkdir(parents=True)
    monkeypatch.setenv("ZOZA_DIR", str(tmp_path / "zoza"))
    from app.agents import register_all_agents

    register_all_agents()
    await zoza_queues.enqueue_zoza({"package": sample_content_package}, settings)
    assert await worker_module.run_zoza_queue_once("fp:queue:zoza") is True
    from sqlalchemy import func, select

    from app.db.models.zoza import ZozaRequest

    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(ZozaRequest))).scalar() == 1


async def test_worker_empty_zoza_queue_returns_false(monkeypatch):
    _fake_redis(monkeypatch)
    assert await worker_module.run_zoza_queue_once("fp:queue:zoza") is False


async def test_all_queue_names_distinct():
    from app.queue import content_queues, decision_queues, intel_queues

    all_names = (set(zoza_queues.QUEUE_TO_AGENT)
                 | set(content_queues.QUEUE_TO_AGENT)
                 | set(decision_queues.QUEUE_TO_AGENT)
                 | set(intel_queues.QUEUE_TO_AGENT))
    assert len(all_names) == 15
    assert "fp:queue:render" not in all_names
    assert "fp:queue:creative" not in all_names
