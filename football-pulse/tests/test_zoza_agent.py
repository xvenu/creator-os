"""Zoza refactor tests: dispatcher agent — submit/track/export/retry + events."""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentStatus
from app.db.models.zoza import FactoryStatus, ZozaExport, ZozaRequest
from app.modules.zoza_client import events
from app.modules.zoza_client.agent import ZozaDispatcherAgent


@pytest.fixture
def zoza_env(tmp_path, monkeypatch):
    jobs = tmp_path / "zoza" / "jobs"
    jobs.mkdir(parents=True)
    monkeypatch.setenv("ZOZA_DIR", str(tmp_path / "zoza"))
    events.clear_outbox()
    return tmp_path / "zoza"


def _factory_state(zoza_dir, job_id, state):
    path = zoza_dir / "jobs" / f"{job_id}.json"
    job = json.loads(path.read_text())
    job["state"] = state
    path.write_text(json.dumps(job))


async def test_submit_package_creates_request_and_job_file(
    session_factory, zoza_env, sample_content_package,
):
    result = await ZozaDispatcherAgent().run(
        AgentContext(payload={"package": sample_content_package}))
    assert result.status == AgentStatus.SUCCEEDED
    out = result.output
    assert out["state"] in ("submitted", "queued", "rendering", "rendered")
    assert (zoza_env / "jobs" / f"{out['zoza_job_id']}.json").exists()
    kinds = [e["event_type"] for e in events.outbox()]
    assert "VIDEO_REQUESTED" in kinds
    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(ZozaRequest))).scalar() == 1
        status = (await session.execute(select(FactoryStatus))).scalars().all()
        assert status and status[0].reachable is True


async def test_submit_idempotent_for_same_package(
    session_factory, zoza_env, sample_content_package,
):
    agent = ZozaDispatcherAgent()
    first = await agent.run(AgentContext(payload={"package": sample_content_package}))
    second = await agent.run(AgentContext(payload={"package": sample_content_package}))
    assert first.output["request_id"] == second.output["request_id"]
    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(ZozaRequest))).scalar() == 1


async def test_monitor_collects_rendered_export(
    session_factory, zoza_env, sample_content_package,
):
    agent = ZozaDispatcherAgent()
    made = await agent.run(AgentContext(payload={"package": sample_content_package}))
    job_id, request_id = made.output["zoza_job_id"], made.output["request_id"]
    _factory_state(zoza_env, job_id, "RENDERED")
    outdir = zoza_env / "output" / job_id
    outdir.mkdir(parents=True)
    (outdir / "final.mp4").write_bytes(b"v")
    (outdir / "thumb.png").write_bytes(b"t")
    result = await agent.run(AgentContext(payload={"request_id": request_id}))
    assert result.output["state"] == "exported"
    assert result.output["export"]["video_path"].endswith("final.mp4")
    kinds = [e["event_type"] for e in events.outbox()]
    assert "VIDEO_RENDER_FINISHED" in kinds and "VIDEO_EXPORTED" in kinds
    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(ZozaExport))).scalar() == 1


async def test_factory_unreachable_stays_retryable(
    session_factory, tmp_path, monkeypatch, sample_content_package,
):
    monkeypatch.setenv("ZOZA_DIR", str(tmp_path / "missing"))
    events.clear_outbox()
    result = await ZozaDispatcherAgent().run(
        AgentContext(payload={"package": sample_content_package}))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["submitted"] is False
    assert result.output["state"] == "created"  # NOT failed — retryable


async def test_failed_factory_job_marks_request_failed(
    session_factory, zoza_env, sample_content_package,
):
    agent = ZozaDispatcherAgent()
    made = await agent.run(AgentContext(payload={"package": sample_content_package}))
    _factory_state(zoza_env, made.output["zoza_job_id"], "FAILED")
    result = await agent.run(AgentContext(payload={"request_id": made.output["request_id"]}))
    assert result.output["state"] == "failed"


async def test_retry_exhaustion_fails_closed(session_factory, zoza_env, sample_content_package):
    from app.modules.zoza_client.store import get_request_by_job

    agent = ZozaDispatcherAgent()
    made = await agent.run(AgentContext(payload={"package": sample_content_package}))
    request_id = made.output["request_id"]
    last = None
    for _ in range(6):
        last = await agent.run(AgentContext(payload={"retry_request_id": request_id}))
    assert last.output["state"] == "failed"
    assert last.output["attempts"] >= 5


async def test_retry_unknown_request_fails(session_factory):
    result = await ZozaDispatcherAgent().run(AgentContext(payload={
        "retry_request_id": "00000000-0000-0000-0000-000000000000"}))
    assert result.status == AgentStatus.FAILED


async def test_request_transition_guard(session_factory):
    from app.modules.zoza_client.store import create_request, transition_request

    async with session_factory() as session:
        row = await create_request(session, None, "fp-guard", {}, 0)
        await transition_request(session, row, "submitted")
        with pytest.raises(ValueError):
            await transition_request(session, row, "exported")  # skip forbidden
        await session.rollback()


def test_shared_bus_forwarding_opt_in(tmp_path, monkeypatch):
    from app.modules.zoza_client import events as ev

    events.clear_outbox()
    monkeypatch.delenv("FOOTBALLPULSE_SHARED_BUS", raising=False)
    ev.emit("VIDEO_REQUESTED", {"t": 1})
    assert len(events.outbox()) == 1  # local outbox always records
    # Opt-in path forwards without raising (fail-open verified separately).
    monkeypatch.setenv("FOOTBALLPULSE_SHARED_BUS", "1")
    ev.emit("VIDEO_REQUESTED", {"t": 2})
    import sqlite3

    db = tmp_path  # placeholder to keep linters quiet about unused import
    _ = db
    from pathlib import Path

    bus = Path(__file__).resolve().parents[2] / "shared" / "event_bus" / "event_bus.db"
    conn = sqlite3.connect(bus)
    try:
        n = conn.execute(
            "select count(*) from events where source_pulse='football-pulse'").fetchone()[0]
        assert n >= 1
        conn.execute("delete from events where source_pulse='football-pulse'")
        conn.commit()
    finally:
        conn.close()
