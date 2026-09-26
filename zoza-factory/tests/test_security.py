"""Security: traversal, malformed, ownership, no credential surfaces."""
from __future__ import annotations

from tests.conftest import make_request


def test_path_traversal_request_id_rejected_or_isolated(client, tmp_path):
    body = make_request(request_id="../evil", length_seconds=20)
    r = client.post("/api/v1/requests", json=body)
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        export = client.post("/api/v1/requests/..%2Fevil/execute")
        assert export.status_code in (404, 422)
        import os
        assert not os.path.exists(os.path.join(str(tmp_path), "evil", "video.mp4"))


def test_malformed_bodies_rejected(client):
    assert client.post("/api/v1/requests", json={}).status_code == 422
    assert client.post("/api/v1/requests", json={"request_id": "m1"}).status_code == 422
    bad = make_request(request_id="m2", length_seconds=-5)
    assert client.post("/api/v1/requests", json=bad).status_code == 422


def test_exports_events_logs_carry_no_credentials(client):
    body = make_request(request_id="req-sec-1", length_seconds=20)
    assert client.post("/api/v1/requests", json=body).status_code == 200
    export = client.post("/api/v1/requests/req-sec-1/execute").json()
    blob = str(export)
    for marker in ("TOKEN", "SECRET", "BEARER", "AKIA", "sk-live"):
        assert marker not in blob.upper().replace("TONE", "")
    row = client.get("/api/v1/requests/req-sec-1").json()
    assert "token" not in str(row).lower() or "tone" in str(row).lower()


def test_reality_only_rejects_ai_only_universe(client):
    body = make_request(request_id="req-sec-ro", production_mode="REALITY_ONLY",
                        length_seconds=20)
    assert client.post("/api/v1/requests", json=body).status_code == 200
    plan = client.post("/api/v1/requests/req-sec-ro/plan").json()
    assert plan["ai_generation_allowed_effective"] is False
    assert plan["strategy"]["ai_ratio"] == 0.0


def test_real_media_required_honored(client):
    body = make_request(request_id="req-sec-rmr", production_mode="REALITY_FIRST",
                        ai_generation_allowed=True, length_seconds=20,
                        asset_requirements={"real_media_required": True,
                                            "preferred_types": ["official_photo"],
                                            "reason": "artist likeness must be real"})
    assert client.post("/api/v1/requests", json=body).status_code == 200
    plan = client.post("/api/v1/requests/req-sec-rmr/plan").json()
    assert plan["ai_generation_allowed_effective"] is False
    assert plan["real_media_required"] is True
    assert plan["real_media_honored"] is True
    assert all(a["kind"] not in ("ai_generated", "ai_video", "ai_image")
               for a in plan["assets"])
    assert all("provenance" in a and "content_hash" in a and "acquired_at" in a
               for a in plan["assets"])
