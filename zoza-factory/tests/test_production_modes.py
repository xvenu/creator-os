"""§12: production-mode tests — REALITY_ONLY / REALITY_FIRST / HYBRID / AI_CREATIVE."""
from __future__ import annotations

from tests.conftest import REAL_EVIDENCE, REAL_SOURCES, make_request


def test_reality_only_uses_real_assets_only(client):
    body = make_request(request_id="req-mode-reality-only",
                        production_mode="REALITY_ONLY",
                        ai_generation_allowed=False,
                        sources=REAL_SOURCES, evidence=REAL_EVIDENCE)
    assert client.post("/api/v1/requests", json=body).status_code == 200
    plan = client.post("/api/v1/requests/req-mode-reality-only/plan").json()
    kinds = {a["kind"] for a in plan["assets"]}
    assert "ai_generated" not in kinds
    assert plan["strategy"]["ai_ratio"] == 0.0
    assert plan["strategy"]["reality_ratio"] == 1.0


def test_reality_only_never_injects_ai_when_empty(client):
    body = make_request(request_id="req-mode-reality-only-empty",
                        production_mode="REALITY_ONLY",
                        goal="Obscure topic with no coverage whatsoever.")
    assert client.post("/api/v1/requests", json=body).status_code == 200
    plan = client.post("/api/v1/requests/req-mode-reality-only-empty/plan").json()
    assert plan["ai_fallback_injected"] is False
    assert all(a["kind"] != "ai_generated" for a in plan["assets"])


def test_reality_first_prefers_real_over_ai(client):
    body = make_request(request_id="req-mode-reality-first",
                        production_mode="REALITY_FIRST",
                        ai_generation_allowed=True,
                        sources=REAL_SOURCES, evidence=REAL_EVIDENCE)
    assert client.post("/api/v1/requests", json=body).status_code == 200
    plan = client.post("/api/v1/requests/req-mode-reality-first/plan").json()
    first_kind = plan["assets"][0]["kind"]
    assert first_kind in ("real_footage", "real_photo")  # hierarchy respected
    assert plan["strategy"]["reality_ratio"] >= plan["strategy"]["ai_ratio"]


def test_reality_first_no_ai_when_disallowed(client):
    body = make_request(request_id="req-mode-reality-first-noai",
                        production_mode="REALITY_FIRST",
                        ai_generation_allowed=False)
    assert client.post("/api/v1/requests", json=body).status_code == 200
    plan = client.post("/api/v1/requests/req-mode-reality-first-noai/plan").json()
    assert plan["ai_generation_allowed_effective"] is False
    assert all(a["kind"] != "ai_generated" for a in plan["assets"])


def test_hybrid_allows_ai_mix(client):
    body = make_request(request_id="req-mode-hybrid",
                        production_mode="HYBRID",
                        sources=REAL_SOURCES, evidence=REAL_EVIDENCE)
    assert client.post("/api/v1/requests", json=body).status_code == 200
    plan = client.post("/api/v1/requests/req-mode-hybrid/plan").json()
    assert plan["ai_generation_allowed_effective"] is True
    assert plan["strategy"]["strategy"] in ("hybrid-mix", "hybrid-full-reality")


def test_ai_creative_allows_generation(client):
    body = make_request(request_id="req-mode-ai-creative",
                        production_mode="AI_CREATIVE",
                        goal="A fictional animated intro.")
    assert client.post("/api/v1/requests", json=body).status_code == 200
    plan = client.post("/api/v1/requests/req-mode-ai-creative/plan").json()
    assert plan["ai_generation_allowed_effective"] is True
    assert plan["strategy"]["strategy"] in ("ai-creative", "ai-fallback", "hybrid-mix",
                                            "reality-first-mixed", "reality-first-full-reality",
                                            "hybrid-full-reality")
