"""§12: rights validation, timeline matching, voice matching, strategy generation."""
from __future__ import annotations


def test_rights_blocked_assets_excluded(client):
    res = client.post("/api/v1/rights/validate", json={
        "rights_status": "BLOCKED", "license": "prohibited",
        "production_mode": "HYBRID"})
    body = res.json()
    assert body["status"] == "BLOCKED"
    assert body["usable_in_mode"]["HYBRID"] is False
    assert body["usable_in_mode"]["REALITY_ONLY"] is False


def test_rights_unknown_flagged_and_excluded_from_reality_only(client):
    res = client.post("/api/v1/rights/validate", json={
        "rights_status": "UNKNOWN", "license": "",
        "production_mode": "REALITY_ONLY"})
    body = res.json()
    assert body["status"] == "UNKNOWN"
    assert body.get("needs_review") is True
    assert body["usable_in_mode"]["REALITY_ONLY"] is False
    assert body["usable_in_mode"]["HYBRID"] is True  # flagged but allowed elsewhere


def test_rights_batch_blocks_violations(client):
    res = client.post("/api/v1/rights/validate", json={
        "production_mode": "REALITY_FIRST",
        "assets": [
            {"source": "good", "license": "public-domain",
             "trust_score": 0.9, "rights_status": "CLEARED", "kind": "public_domain"},
            {"source": "bad", "license": "prohibited do-not-use",
             "trust_score": 0.9, "rights_status": "BLOCKED", "kind": "real_photo"},
        ]})
    body = res.json()
    assert body["summary"] == {"usable": 1, "blocked": 1, "total": 2}
    assert body["usable"][0]["source"] == "good"
    assert body["blocked"][0]["source"] == "bad"


def test_timeline_matches_narration_length(client):
    res = client.post("/api/v1/timeline/build", json={
        "narration": "Burna Boy rose from Port Harcourt. He won the Grammy in 2021. His sound spans continents.",
        "length_seconds": 45,
        "assets": [{"source": "a", "kind": "real_footage"},
                   {"source": "b", "kind": "real_photo"}]})
    body = res.json()
    assert body["total_seconds"] == 45
    assert body["matches_narration"] is True
    assert body["overrun_seconds"] == 0.0
    assert body["underrun_seconds"] == 0.0
    assert body["scene_count"] >= 1
    assert " --> " in body["subtitles_srt"]  # valid SRT cues


def test_timeline_detects_gaps_without_assets(client):
    res = client.post("/api/v1/timeline/build", json={
        "narration": "One. Two. Three.",
        "length_seconds": 30, "assets": []})
    body = res.json()
    assert body["gap_count"] == body["scene_count"]
    assert body["total_seconds"] == 30  # still exact


def test_voice_matching_sports(client):
    res = client.post("/api/v1/voice/match", json={
        "goal": "Create a tactical analysis of Arsenal.",
        "target_audience": "football fans"})
    assert res.json()["profile"] == "sports-analysis"


def test_voice_matching_history_and_explicit(client):
    historical = client.post("/api/v1/voice/match", json={
        "goal": "A historical story from the public-domain archive."}).json()
    assert historical["profile"] == "historical-story"
    explicit = client.post("/api/v1/voice/match", json={
        "voice_profile": "breaking-news", "goal": "Something else."}).json()
    assert explicit["profile"] == "breaking-news"


def test_strategy_generation_shape(client):
    from tests.conftest import REAL_SOURCES, make_request
    body = make_request(request_id="req-strategy-shape",
                        sources=REAL_SOURCES, ai_generation_allowed=True)
    assert client.post("/api/v1/requests", json=body).status_code == 200
    plan = client.post("/api/v1/requests/req-strategy-shape/plan").json()
    strat = plan["strategy"]
    assert strat["reality_ratio"] + strat["ai_ratio"] == 1.0
    assert strat["estimated_runtime"] > 0
    assert strat["asset_sources"]
    assert strat["explanation"]
    assert strat["asset_strategy"] and strat["voice_strategy"]
    assert strat["timeline_strategy"] and strat["render_strategy"]
