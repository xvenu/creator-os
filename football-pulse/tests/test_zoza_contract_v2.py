"""Football Contract V2 wiring: native package -> factory -> export."""
from __future__ import annotations

import os

from app.modules.zoza_client.adapter import FakeFactoryTransport, FootballZozaAdapter
from app.modules.zoza_client import events
from app.modules.zoza_client.mapper import (
    FootballProductionMapper,
    decide_production_mode,
    map_package_to_contract,
)
from app.modules.zoza_client.tracker import FootballZozaTracker


def _pkg(**overrides):
    base = {
        "package_id": "11111111-1111-1111-1111-111111111111",
        "topic": "Arsenal record signing",
        "title": "Arsenal Record Signing — Transfer Update",
        "summary": "Arsenal confirmed a record signing on deadline day.",
        "content_type": "transfer_update",
        "script": {"hook": "It's happening.",
                   "body": "Arsenal confirmed a record signing.",
                   "outro": "Subscribe."},
        "seo": {"hashtags": ["#football", "#arsenal"]},
        "thumbnail": {"thumbnail_text": "DONE DEAL"},
        "regions": ["UK", "US"],
        "quality": {"overall_score": 0.85},
        "opportunity_score": 0.85,
        "platform_targets": ["youtube", "tiktok"],
    }
    base.update(overrides)
    return base


def test_map_transfer_breaking():
    out = map_package_to_contract(_pkg())
    assert out["style"] == "sports news"
    assert out["urgency"] == "high"
    assert out["target_audience"] == "UK"
    assert out["priority"] == 85
    assert any(s.get("type") == "real_world_asset_request" for s in out["sources"])


def test_map_styles():
    assert map_package_to_contract(
        _pkg(content_type="match_analysis", title="Arsenal vs Chelsea"))["style"] == "sports analysis"
    assert map_package_to_contract(
        _pkg(content_type="player_biography", title="Saka story"))["style"] == "documentary"
    assert map_package_to_contract(
        _pkg(content_type="tactical_breakdown", title="Arteta tactics"))["style"] == "analysis"
    assert map_package_to_contract(
        _pkg(content_type="historical", title="Invincibles"))["style"] == "documentary"


def test_mode_decisions_pulse_owned():
    assert decide_production_mode(_pkg(title="Player interview: Saka")) == "REALITY_ONLY"
    assert decide_production_mode(
        _pkg(title="Tactical breakdown with diagrams")) == "HYBRID"
    assert decide_production_mode(
        _pkg(title="Anime concept", ai_generation_allowed=True)) == "AI_CREATIVE"
    assert decide_production_mode(_pkg(), "FIRST") == "REALITY_FIRST"
    mapper = FootballProductionMapper()
    assert mapper.to_contract(_pkg())["pulse"] == "football-pulse"


def test_idempotent_submission():
    adapter = FootballZozaAdapter(transport=FakeFactoryTransport(),
                                  tracker=FootballZozaTracker())
    pkg = _pkg()
    first = adapter.submit_package(pkg)
    second = adapter.submit_package(pkg)
    assert first["submitted"] and second["reused"]
    assert first["request_id"] == second["request_id"]


def test_poll_and_export():
    adapter = FootballZozaAdapter(transport=FakeFactoryTransport(),
                                  tracker=FootballZozaTracker())
    rid = adapter.submit_package(_pkg())["request_id"]
    for state in ("planned", "acquiring", "assembling", "rendering", "exported"):
        adapter.transport.set_state(rid, state)
        assert adapter.poll(rid)["state"] == state
    consumed = adapter.consume_export(rid)
    assert consumed["ok"] and consumed["export"]["status"] == "rendered"


def test_unreachable_retryable():
    adapter = FootballZozaAdapter(transport=FakeFactoryTransport(unreachable=True),
                                  tracker=FootballZozaTracker())
    out = adapter.submit_package(_pkg())
    assert out["submitted"] is False and out["retryable"] is True
    adapter.transport.unreachable = False
    assert adapter.retry(out["request_id"])["state"] == "created"


def test_failed_retryable_and_exhaustion():
    adapter = FootballZozaAdapter(transport=FakeFactoryTransport(),
                                  tracker=FootballZozaTracker(), max_attempts=1)
    rid = adapter.submit_package(_pkg())["request_id"]
    adapter.transport.set_state(rid, "failed")
    assert adapter.poll(rid)["state"] == "failed"
    adapter.retry(rid)
    assert adapter.retry(rid)["state"] == "failed"


def test_events_and_boundaries():
    events.clear_outbox()
    adapter = FootballZozaAdapter(transport=FakeFactoryTransport(),
                                  tracker=FootballZozaTracker())
    adapter.submit_package(_pkg())
    assert any(e["event_type"] == "VIDEO_REQUESTED" for e in events.outbox())
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app",
                        "modules", "zoza_client")
    blob = ""
    for fname in os.listdir(root):
        if fname.endswith(".py") and fname in ("adapter.py", "mapper.py", "tracker.py"):
            with open(os.path.join(root, fname)) as fh:
                for line in fh:
                    s = line.strip()
                    if s.startswith('"""') or s.startswith("#") or s.startswith("*"):
                        continue
                    blob += line.lower()
    for banned in ("import ffmpeg", "from ffmpeg", "import moviepy", "import cv2",
                   "render_video(", "youtubeuploader", "tiktokuploader",
                   "instagramuploader", "facebookuploader", "channeluploader"):
        assert banned not in blob, f"Contract V2 adapter must not contain {banned}"
    with open(os.path.join(root, "mapper.py")) as fh:
        assert "class ProductionRequestIn" not in fh.read()
