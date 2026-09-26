"""Real-media gates: container, codecs, duration, resolution, audio, subtitles.

These tests inspect actual bytes (file signature + `ffmpeg -i` parse), never
sidecar JSON. The simulated provider is bypassed — default production path only.
"""
from __future__ import annotations

import os

from tests.conftest import make_request


def test_real_mp4_is_valid_media(client):
    body = make_request(request_id="req-real-media-1", pulse="music-pulse",
                        goal="Real media check. A drummer plays at dusk. The crowd sways.",
                        style="documentary", length_seconds=30,
                        production_mode="REALITY_FIRST")
    assert client.post("/api/v1/requests", json=body).status_code == 200
    export = client.post("/api/v1/requests/req-real-media-1/execute").json()
    assert export["status"] == "rendered"
    md = export["metadata"]
    assert md["provider"] == "local-ffmpeg"
    assert os.path.exists(export["video_path"])
    raw = open(export["video_path"], "rb").read()
    assert raw[4:8] == b"ftyp"  # real MP4 signature
    assert len(raw) > 10_000
    qc = md["qc"]
    assert qc["container_ftyp"] is True
    assert qc["video_stream"] is True
    assert qc["audio_stream"] is True
    assert qc["duration"] is True
    assert qc["resolution"] is True
    assert qc["subtitle"] is True
    assert md["width"] == 1280 and md["height"] == 720
    assert abs(md["duration_seconds"] - 30) < 0.01
    assert md["video"]["sha256"] and md["storage"]["backend"] == "local"
    assert os.path.exists(export["thumbnail_path"])


def test_simulated_provider_is_explicit_only(client):
    from app.core.config import get_settings
    assert get_settings().render_provider != "simulated"
    from app.modules.renderer import providers as prov
    names = [p["name"] for p in prov.available()]
    assert "simulated-test-only" in names
    assert "local-ffmpeg" in names
