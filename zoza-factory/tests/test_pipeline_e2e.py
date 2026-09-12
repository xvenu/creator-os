"""End-to-end pipeline, capacity, contract compliance, and guardrail tests."""
from __future__ import annotations

import os

from tests.conftest import REAL_EVIDENCE, REAL_SOURCES, make_request


def test_full_pipeline_music_documentary(client):
    body = make_request(request_id="req-e2e-music",
                        pulse="music-pulse",
                        goal="Create a documentary about Burna Boy.",
                        style="documentary", length_seconds=60,
                        production_mode="REALITY_FIRST",
                        sources=REAL_SOURCES, evidence=REAL_EVIDENCE,
                        voice_profile="documentary")
    assert client.post("/api/v1/requests", json=body).status_code == 200
    export = client.post("/api/v1/requests/req-e2e-music/execute").json()
    assert export["status"] == "rendered"  # factory never publishes
    assert export["job_id"] == "req-e2e-music"
    assert os.path.exists(export["video_path"])
    assert os.path.exists(export["thumbnail_path"])
    row = client.get("/api/v1/requests/req-e2e-music").json()
    assert row["state"] == "exported"
    # Video duration matches narration length.
    assert row["timeline"]["total_seconds"] == 60
    assert row["timeline"]["matches_narration"] is True


def test_full_pipeline_football_tactical(client):
    body = make_request(request_id="req-e2e-football",
                        pulse="football-pulse",
                        goal="Create a tactical analysis of Arsenal.",
                        style="sports-analysis", length_seconds=45,
                        production_mode="HYBRID",
                        target_audience="football fans")
    assert client.post("/api/v1/requests", json=body).status_code == 200
    export = client.post("/api/v1/requests/req-e2e-football/execute").json()
    assert export["status"] == "rendered"
    row = client.get("/api/v1/requests/req-e2e-football").json()
    assert row["state"] == "exported"
    assert row["timeline"]["total_seconds"] == 45


def test_export_conforms_to_shared_contract():
    """Every factory export must pass shared/contracts.py::validate_export."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/..")
    from shared.contracts import validate_export
    from tests.conftest import _TEST_DIR
    import json
    for req_id in ("req-e2e-music", "req-e2e-football"):
        path = os.path.join(_TEST_DIR, "output", req_id, "export.json")
        with open(path) as f:
            validate_export(json.load(f))


def test_capacity_report_shape(client):
    body = client.get("/api/v1/capacity").json()
    for field in ("active_jobs", "queued_jobs", "average_render_time",
                  "average_export_time", "provider_availability",
                  "asset_availability"):
        assert field in body, f"capacity missing {field}"
    assert "render" in body["provider_availability"]
    assert "voice" in body["provider_availability"]
    assert "assets" in body["provider_availability"]
    assert body["asset_availability"]["total"] >= 4  # seed catalog


def test_contract_v2_has_no_business_fields():
    """Guardrail: Contract V2 carries intent only — no publishing, audience
    ownership, or revenue fields. Pulses keep those; Zoza never sees them."""
    from app.schemas.contract import ProductionRequestIn
    fields = set(ProductionRequestIn.model_fields)
    forbidden = {"publish_targets", "publish", "audience_owned", "followers",
                 "revenue", "monetization", "price", "sponsor", "upload",
                 "youtube", "tiktok", "telegram"}
    assert not (fields & forbidden), f"contract leak: {fields & forbidden}"
    required = {"request_id", "goal", "style", "length_seconds", "urgency",
                "production_mode", "ai_generation_allowed", "sources",
                "evidence", "voice_profile", "target_audience", "priority"}
    assert required <= fields


def test_renderer_has_no_publishing_path():
    """Guardrail: the renderer module must contain no publishing surface."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "app", "modules", "renderer", "engine.py")
    with open(path) as f:
        code = f.read().lower()
    for marker in ("def publish", "publish(", "upload(", "youtube",
                   "tiktok", "telegram", "revenue", "sponsor"):
        assert marker not in code, f"renderer leak: {marker}"
