"""Real end-to-end per pulse: request → plan → render → QC → export (no publish)."""
from __future__ import annotations

import os

from tests.conftest import REAL_EVIDENCE, REAL_SOURCES, make_request


def _run_real(client, body):
    assert client.post("/api/v1/requests", json=body).status_code == 200
    plan = client.post(f"/api/v1/requests/{body['request_id']}/plan").json()
    assert plan["timeline"]["matches_narration"] is True
    export = client.post(f"/api/v1/requests/{body['request_id']}/execute").json()
    assert export["status"] == "rendered"
    return export


def test_music_reality_first_real_media(client):
    body = make_request(request_id="req-real-music", pulse="music-pulse",
                        goal="Documentary portrait. A guitarist plays in Lagos. Crowds gather at dusk.",
                        style="documentary", length_seconds=30,
                        production_mode="REALITY_FIRST",
                        sources=REAL_SOURCES, evidence=REAL_EVIDENCE,
                        voice_profile="documentary",
                        asset_requirements={"real_media_required": True,
                                            "reason": "artist likeness must be real"})
    export = _run_real(client, body)
    md = export["metadata"]
    assert md["pulse"] == "music-pulse" and md["provider"] == "local-ffmpeg"
    assert md["qc"]["video_stream"] and md["qc"]["audio_stream"] and md["qc"]["duration"]
    assert md["real_image_scenes"] >= 1
    assert os.path.exists(export["video_path"])
    for banned in ("youtube", "tiktok", "publish", "revenue"):
        assert banned not in str(export).lower()


def test_football_reality_first_real_media(client):
    body = make_request(request_id="req-real-football", pulse="football-pulse",
                        goal="Tactical breakdown. Arsenal press high. The striker times the run.",
                        style="sports-analysis", length_seconds=30,
                        production_mode="REALITY_FIRST",
                        sources=REAL_SOURCES, target_audience="football fans")
    export = _run_real(client, body)
    assert export["metadata"]["pulse"] == "football-pulse"
    assert export["metadata"]["qc"]["resolution"] is True
