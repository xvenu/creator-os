"""Cross-pulse wiring: both Pulses -> Zoza Contract V2 -> export.

Proves the responsibility split end-to-end against the real factory
pipeline: Pulses decide WHAT, Zoza decides HOW and never publishes.
"""
from __future__ import annotations

import os
import sys

CREATOR_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# tests file is zoza-factory/tests/test_pulse_wiring.py -> creator-os/
for _p in (os.path.join(CREATOR_ROOT, "music-pulse"),
           os.path.join(CREATOR_ROOT, "football-pulse"),
           CREATOR_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tests.conftest import REAL_EVIDENCE, REAL_SOURCES, make_request  # noqa: E402

PREFIX = "/api/v1"


def _submit_and_run(client, payload):
    r = client.post(f"{PREFIX}/requests", json=payload)
    assert r.status_code == 200, r.text
    rid = r.json()["request_id"]
    r = client.post(f"{PREFIX}/requests/{rid}/plan")
    assert r.status_code == 200, r.text
    r = client.post(f"{PREFIX}/requests/{rid}/execute")
    assert r.status_code == 200, r.text
    export = r.json()
    assert export["status"] == "rendered"
    r = client.get(f"{PREFIX}/exports/{rid}")
    assert r.status_code == 200
    return rid, export


def test_music_and_football_concurrent_exports(client):
    music = make_request(
        request_id="req-music-v2-001", pulse="music-pulse",
        goal="news video: Nova explodes", style="news", length_seconds=60,
        urgency="high", production_mode="REALITY_FIRST",
        sources=REAL_SOURCES, evidence=REAL_EVIDENCE,
        voice_profile="news", target_audience="US", priority=88)
    football = make_request(
        request_id="req-football-v2-001", pulse="football-pulse",
        goal="transfer news: Osimhen to Arsenal", style="sports news",
        length_seconds=60, urgency="high", production_mode="REALITY_FIRST",
        sources=REAL_SOURCES, evidence=REAL_EVIDENCE,
        voice_profile="energetic", target_audience="UK", priority=85)
    mid, mexp = _submit_and_run(client, music)
    fid, fexp = _submit_and_run(client, football)
    assert mid != fid
    assert mexp["metadata"]["pulse"] == "music-pulse"
    assert fexp["metadata"]["pulse"] == "football-pulse"
    # Export carries production evidence; publishing fields must not exist.
    for exp in (mexp, fexp):
        assert "video_path" in exp and "thumbnail_path" in exp
        assert os.path.exists(exp["video_path"])
        for banned in ("youtube", "tiktok", "publish", "revenue", "credentials"):
            assert banned not in str(exp).lower()


def test_factory_never_publishes(client):
    payload = make_request(request_id="req-nopub-001")
    _, export = _submit_and_run(client, payload)
    assert export["status"] == "rendered"
    assert set(export) == {"job_id", "status", "video_path", "thumbnail_path", "metadata"}


def test_pulse_mappers_produce_valid_contracts(client):
    import importlib.util

    def _load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    music_mod = _load("music_mapper_v2", os.path.join(
        CREATOR_ROOT, "music-pulse", "app", "modules", "zoza_client", "mapper.py"))
    m = music_mod.map_package_to_contract(
        {"id": "pkg-x-1", "type": "news", "title": "Nova story",
         "script": "hook body outro", "target_market": "US", "priority_score": 50})
    m["request_id"] = "req-map-music-001"
    r = client.post(f"{PREFIX}/requests", json=m)
    assert r.status_code == 200, r.text

    fmod = _load("football_mapper_v2", os.path.join(
        CREATOR_ROOT, "football-pulse", "app", "modules", "zoza_client", "mapper.py"))
    f = fmod.map_package_to_contract({
        "package_id": "22222222-2222-2222-2222-222222222222",
        "topic": "Arsenal signing", "title": "Arsenal signing",
        "content_type": "transfer_update",
        "script": {"hook": "H", "body": "B", "outro": "O"},
        "regions": ["UK"], "opportunity_score": 0.8})
    f["request_id"] = "req-map-football-001"
    r = client.post(f"{PREFIX}/requests", json=f)
    assert r.status_code == 200, r.text


def test_architectural_guardrails():
    fac_root = os.path.join(CREATOR_ROOT, "zoza-factory", "app")
    fac_blob = ""
    for base, _, files in os.walk(fac_root):
        for fn in files:
            if fn.endswith(".py"):
                with open(os.path.join(base, fn)) as fh:
                    fac_blob += fh.read().lower()
    for banned in ("youtubeuploader", "tiktokuploader", "instagramuploader",
                   "facebookuploader", "channeluploader", "youtube_api_key",
                   "tiktok_session"):
        assert banned not in fac_blob, f"factory must not contain {banned}"

    for pulse in ("music-pulse", "football-pulse"):
        client_dir = os.path.join(CREATOR_ROOT, pulse, "app", "modules", "zoza_client")
        blob = ""
        for fn in os.listdir(client_dir):
            if fn.endswith(".py") and fn in ("adapter.py", "mapper.py", "tracker.py"):
                with open(os.path.join(client_dir, fn)) as fh:
                    for line in fh:
                        s = line.strip()
                        if s.startswith('"""') or s.startswith("#") or s.startswith("*"):
                            continue
                        blob += line.lower()
        assert "import ffmpeg" not in blob, f"{pulse} adapter must not render"
        assert "class productionrequestin" not in blob
