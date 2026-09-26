"""Universal factory: anime / real / AI / movie / ads for ANY pulse."""
from __future__ import annotations

import os

from tests.conftest import make_request

PREFIX = "/api/v1"


def _run(client, body):
    r = client.post(f"{PREFIX}/requests", json=body)
    assert r.status_code == 200, r.text
    rid = body["request_id"]
    r = client.post(f"{PREFIX}/requests/{rid}/execute")
    assert r.status_code == 200, r.text
    return r.json()


def test_anime_pulse_end_to_end(client):
    body = make_request(request_id="req-uni-anime", pulse="anime-pulse",
                        goal="Anime episode: a brave courier crosses the neon city.",
                        style="anime", length_seconds=60, production_mode="HYBRID",
                        ai_generation_allowed=True, content_type="anime",
                        format_variant="episode")
    export = _run(client, body)
    assert export["status"] == "rendered"
    assert export["metadata"]["content_type"] == "anime"
    row = client.get(f"{PREFIX}/requests/req-uni-anime").json()
    assert row["timeline"]["structure"] == "cold_open-beats-tag"
    assert row["timeline"]["matches_narration"] is True
    assert os.path.exists(export["video_path"])


def test_movie_three_acts(client):
    body = make_request(
        request_id="req-uni-movie", pulse="movie-pulse",
        goal="Feature story. A family returns home. They face the storm. They rebuild together.",
        style="cinematic", length_seconds=120, production_mode="REALITY_FIRST",
        content_type="movie", format_variant="feature", narration="")
    export = _run(client, body)
    assert export["metadata"]["content_type"] == "movie"
    row = client.get(f"{PREFIX}/requests/req-uni-movie").json()
    roles = [s["role"] for s in row["timeline"]["scenes"]]
    assert any(r.startswith("act-") for r in roles)
    assert row["timeline"]["structure"] == "three-acts"


def test_ad_hook_cta(client):
    body = make_request(
        request_id="req-uni-ad", pulse="ads-pulse",
        goal="Launch the new solar lantern for night markets.",
        style="commercial", length_seconds=30, production_mode="HYBRID",
        ai_generation_allowed=True, content_type="ad", format_variant="spot",
        brand_context="SunJar lantern", call_to_action="Get SunJar today.")
    export = _run(client, body)
    assert export["metadata"]["content_type"] == "ad"
    row = client.get(f"{PREFIX}/requests/req-uni-ad").json()
    assert row["timeline"]["structure"] == "hook-body-cta"
    assert row["timeline"]["scenes"][0]["role"] == "hook"
    assert row["timeline"]["scenes"][-1]["role"] == "cta"


def test_ai_film_and_future_pulse(client):
    # A pulse that does not exist yet must still produce.
    reg = client.post(f"{PREFIX}/pulses/register", json={"pulse": "cooking-pulse"})
    assert reg.status_code == 200
    assert reg.json()["registered"] is True
    body = make_request(request_id="req-uni-aifilm", pulse="cooking-pulse",
                        goal="A synthetic feast assembles itself in mid-air.",
                        style="surreal", length_seconds=45,
                        production_mode="AI_CREATIVE",
                        content_type="ai_film")
    export = _run(client, body)
    assert export["metadata"]["content_type"] == "ai_film"
    assert export["metadata"]["pulse"] == "cooking-pulse"


def test_capabilities_advertise_all_families(client):
    caps = client.get(f"{PREFIX}/capabilities").json()
    fams = {c["family"] for c in caps["content_types"]}
    assert {"video", "anime", "movie", "ad", "ai_film"} <= fams
    assert "anime-dub" in caps["voices"] and "commercial" in caps["voices"]
    assert "cinematic-trailer" in caps["voices"]


def test_reality_only_never_ai_even_for_anime(client):
    body = make_request(request_id="req-uni-realonly", pulse="anime-pulse",
                        goal="Hand-drawn festival scene.", length_seconds=30,
                        production_mode="REALITY_ONLY", content_type="anime")
    r = client.post(f"{PREFIX}/requests", json=body)
    assert r.status_code == 200
    plan = client.post(f"{PREFIX}/requests/req-uni-realonly/plan").json()
    assert plan["ai_generation_allowed_effective"] is False
    assert all(a["kind"] not in ("ai_generated", "ai_video", "ai_image")
               for a in plan["assets"])
