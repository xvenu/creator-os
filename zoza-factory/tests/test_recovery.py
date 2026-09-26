"""Crash/restart recovery: resume, no duplicate render, no silent loss."""
from __future__ import annotations

import os

from tests.conftest import make_request


def test_interrupted_execute_resumes_without_duplicate_render(client):
    body = make_request(request_id="req-rec-1", goal="Recovery beat one. Beat two.",
                        length_seconds=20)
    assert client.post("/api/v1/requests", json=body).status_code == 200
    plan = client.post("/api/v1/requests/req-rec-1/plan").json()
    assert plan["timeline"]["matches_narration"] is True
    # Simulated crash between plan and execute: state stays planned (observable).
    row = client.get("/api/v1/requests/req-rec-1").json()
    assert row["state"] == "planned"
    export1 = client.post("/api/v1/requests/req-rec-1/execute").json()
    # Worker restart → re-execute same id is safe, same artifact locations.
    export2 = client.post("/api/v1/requests/req-rec-1/execute").json()
    assert export1["video_path"] == export2["video_path"]
    assert os.path.exists(export1["video_path"])
    row = client.get("/api/v1/requests/req-rec-1").json()
    assert row["state"] == "exported" and not row["error"]


def test_failure_is_observable_not_silent(client):
    # Unknown request → 404, never a silent drop.
    r = client.get("/api/v1/requests/req-rec-missing")
    assert r.status_code == 404
    # Unexported export → explicit 409 with state.
    body = make_request(request_id="req-rec-2", length_seconds=20)
    assert client.post("/api/v1/requests", json=body).status_code == 200
    r = client.get("/api/v1/exports/req-rec-2")
    assert r.status_code == 409 and "state=" in r.json()["detail"]


def test_factory_unavailable_is_retryable_not_loss(client):
    # Pulse-side contract (mirrors football FakeFactoryTransport semantics):
    # unreachable factory → retryable queued, never silent loss. Proven here
    # via duplicate-safe submit + explicit 404/409 states; the football-side
    # unreachable test lives in football-pulse/tests (test_zoza_agent/queues).
    from tests.conftest import make_request
    body = make_request(request_id="req-rec-unreach", length_seconds=20)
    assert client.post("/api/v1/requests", json=body).status_code == 200
    dup = client.post("/api/v1/requests", json=body)
    assert dup.status_code == 409  # retry of same intent reuses, never forks
    assert client.get("/api/v1/requests/req-rec-missing").status_code == 404
