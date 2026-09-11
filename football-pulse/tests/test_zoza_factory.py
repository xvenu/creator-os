"""Zoza refactor tests: factory client against a fake ZOZA_DIR."""
from __future__ import annotations

import json

import pytest

from app.modules.zoza_client.factory import ZozaFactory, map_factory_state, validate_export


@pytest.fixture
def fake_zoza(tmp_path, monkeypatch):
    jobs = tmp_path / "zoza" / "jobs"
    jobs.mkdir(parents=True)
    monkeypatch.setenv("ZOZA_DIR", str(tmp_path / "zoza"))
    return tmp_path / "zoza"


def _write_job(fake_zoza, job_id, state="QUEUED", **extra):
    job = {"job_id": job_id, "title": "T", "state": state, "updated_at": 1.0, **extra}
    (fake_zoza / "jobs" / f"{job_id}.json").write_text(json.dumps(job))
    return job


def test_ping_reachable(fake_zoza):
    ping = ZozaFactory().ping()
    assert ping["reachable"] is True and ping["factory"] == "zoza-video-factory"


def test_ping_unreachable(tmp_path, monkeypatch):
    monkeypatch.setenv("ZOZA_DIR", str(tmp_path / "nope"))
    assert ZozaFactory().ping()["reachable"] is False


def test_state_mapping():
    assert map_factory_state("QUEUED") == "queued"
    assert map_factory_state("ASSEMBLING") == "rendering"
    assert map_factory_state("AWAITING_REVIEW") == "rendered"
    assert map_factory_state("DELIVERED") == "rendered"
    assert map_factory_state("FAILED") == "failed"
    assert map_factory_state("SOMETHING_NEW") == "queued"  # forward-compatible default


def test_submit_writes_and_reuses(fake_zoza):
    factory = ZozaFactory()
    job = {"job_id": "fp-abc123", "state": "QUEUED", "title": "T"}
    first = factory.submit(job)
    assert first["ok"] is True and first["reused"] is False
    second = factory.submit(job)
    assert second["ok"] is True and second["reused"] is True


def test_submit_requires_jobs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ZOZA_DIR", str(tmp_path / "missing"))
    out = ZozaFactory().submit({"job_id": "fp-x"})
    assert out["ok"] is False and out["status"] == "unreachable"


def test_poll_tracks_factory_states(fake_zoza):
    factory = ZozaFactory()
    _write_job(fake_zoza, "fp-1", state="PLANNED")
    assert factory.poll("fp-1")["state"] == "rendering"
    assert factory.poll("fp-ghost")["state"] == "submitted"


def test_collect_export_needs_render_and_files(fake_zoza):
    factory = ZozaFactory()
    _write_job(fake_zoza, "fp-2", state="ASSEMBLING")
    assert factory.collect_export("fp-2")["ok"] is False
    _write_job(fake_zoza, "fp-3", state="RENDERED")
    out = factory.collect_export("fp-3")
    assert out["ok"] is False  # no media files yet
    outdir = fake_zoza / "output" / "fp-3"
    outdir.mkdir(parents=True)
    (outdir / "final.mp4").write_bytes(b"fake-video")
    (outdir / "thumb.png").write_bytes(b"fake-thumb")
    out = factory.collect_export("fp-3")
    assert out["ok"] is True
    export = out["export"]
    assert export["status"] == "rendered" and export["job_id"] == "fp-3"


def test_validate_export_contract():
    good = {"job_id": "j", "status": "rendered", "video_path": "v",
            "thumbnail_path": "t", "metadata": {}}
    assert validate_export(good) == good
    with pytest.raises(ValueError):
        validate_export({**good, "status": "published"})  # factory never publishes
    with pytest.raises(ValueError):
        validate_export({"job_id": "j"})
