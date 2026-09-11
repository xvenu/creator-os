"""Zoza refactor tests: /api/v1/zoza/* endpoints + removal of /videos/*."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def zoza_client(session_factory, tmp_path, monkeypatch):
    jobs = tmp_path / "zoza" / "jobs"
    jobs.mkdir(parents=True)
    monkeypatch.setenv("ZOZA_DIR", str(tmp_path / "zoza"))
    settings = Settings(environment="test", database_url="sqlite+aiosqlite:///:memory:")
    app = create_app(settings)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_request_and_status_flow(zoza_client, sample_content_package):
    r = zoza_client.post("/api/v1/zoza/request", json={"package": sample_content_package})
    assert r.status_code == 200
    request_id = r.json()["request_id"]
    r = zoza_client.get(f"/api/v1/zoza/status/{request_id}")
    assert r.status_code == 200
    assert r.json()["zoza_job_id"].startswith("fp-")
    r = zoza_client.get("/api/v1/zoza/status/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_exports_and_retry_flow(zoza_client, sample_content_package):
    r = zoza_client.post("/api/v1/zoza/request", json={"package": sample_content_package})
    request_id = r.json()["request_id"]
    r = zoza_client.get("/api/v1/zoza/exports")
    assert r.status_code == 200 and r.json()["count"] == 0  # nothing rendered yet
    r = zoza_client.post(f"/api/v1/zoza/retry/{request_id}")
    assert r.status_code == 200
    assert r.json()["request_id"] == request_id


def test_request_rejects_empty_package(zoza_client):
    r = zoza_client.post("/api/v1/zoza/request", json={"package": {"title": ""}})
    assert r.status_code == 422


def test_factory_health_endpoint(zoza_client):
    r = zoza_client.get("/api/v1/zoza/factory")
    assert r.status_code == 200
    assert r.json()["reachable"] is True


def test_local_video_routes_removed(zoza_client):
    for path in ("/api/v1/videos/", "/api/v1/videos/scenes/",
                 "/api/v1/videos/assets/", "/api/v1/videos/renders/",
                 "/api/v1/videos/quality/"):
        assert zoza_client.get(path).status_code == 404, path


def test_no_local_render_path_in_codebase():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    forbidden = ("ffmpeg", "ffprobe", "subprocess", "local_synth", "pil-cards",
                 "video_lifecycle", "scene_service", "subtitle_service",
                 "assembly_service", "quality_service", "creative_service",
                 "voice_service", "visual_service", "run_video_queue",
                 "dequeue_video", "video_queues")
    legacy_files = {"db/models/phase5.py"}  # preserved historical tables
    hits = []
    for path in root.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        rel = str(path.relative_to(root))
        if rel in legacy_files:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            lowered = line.lower()
            if any(t in line for t in forbidden) and not any(
                    marker in lowered for marker in
                    ("deprecat", "historical", "no longer", "preserv", "zoza")):
                hits.append(f"{rel}:{i}: {line.strip()[:100]}")
    assert hits == [], hits
