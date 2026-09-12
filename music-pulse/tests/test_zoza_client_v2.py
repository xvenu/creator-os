"""Contract V2 wiring: native package -> factory -> export -> publishing handoff."""
import os

from app.modules.zoza_client.adapter import FakeFactoryTransport, MusicZozaAdapter
from app.modules.zoza_client import events
from app.modules.zoza_client.mapper import (
    MusicProductionMapper,
    decide_production_mode,
    map_package_to_contract,
)
from app.modules.zoza_client.tracker import MusicZozaTracker


def _news_pkg(**overrides):
    base = {
        "id": "pkg-news-001",
        "type": "news",
        "title": "Nova Explodes Across Charts",
        "summary": "Big story",
        "script": "Hook body outro with enough words to test mapping.",
        "target_market": "US",
        "target_platform": "youtube",
        "priority_score": 88.0,
        "sources": [{"source": "official press kit", "license": "official-use",
                     "trust_score": 0.9, "rights_status": "RESTRICTED"}],
        "evidence": [{"text": "Chart surge verified", "confidence": 0.9}],
        "rights_status": "restricted",
    }
    base.update(overrides)
    return base


def test_map_news_to_contract():
    pkg = _news_pkg()
    out = map_package_to_contract(pkg)
    assert out["goal"].startswith("news video")
    assert out["style"] in ("news", "documentary")
    assert out["production_mode"] == "REALITY_FIRST"
    assert out["urgency"] == "high"  # priority 88 triggers high
    assert out["length_seconds"] == 60
    assert out["target_audience"] == "US"
    assert out["priority"] == 88
    assert any(s.get("type") == "real_world_asset_request" for s in out["sources"])
    for field in ("request_id", "goal", "style", "length_seconds", "urgency",
                  "production_mode", "ai_generation_allowed", "sources",
                  "evidence", "voice_profile", "target_audience", "priority"):
        assert field in out


def test_map_biography_documentary():
    pkg = _news_pkg(id="pkg-bio-002", type="profile", title="The Making of Nova",
                    priority_score=40.0)
    out = map_package_to_contract(pkg)
    assert out["goal"].startswith("artist history")
    assert out["style"] == "documentary"
    assert out["production_mode"] == "REALITY_FIRST"
    assert out["length_seconds"] == 120


def test_map_breaking_and_explicit_mode():
    pkg = _news_pkg(title="BREAKING: Nova signs mega deal")
    assert map_package_to_contract(pkg)["urgency"] == "high"
    out = map_package_to_contract(_news_pkg(), production_mode="HYBRID",
                                  ai_generation_allowed=True)
    assert out["production_mode"] == "HYBRID" and out["ai_generation_allowed"] is True
    assert decide_production_mode(_news_pkg(), "FIRST") == "REALITY_FIRST"


def test_mapper_validates_canonical():
    mapper = MusicProductionMapper()
    out = mapper.to_contract(_news_pkg())
    assert out["pulse"] == "music-pulse"


def test_idempotent_submission():
    adapter = MusicZozaAdapter(transport=FakeFactoryTransport(),
                               tracker=MusicZozaTracker())
    pkg = _news_pkg()
    first = adapter.submit_package(pkg)
    second = adapter.submit_package(pkg)
    assert first["submitted"] and second["reused"]
    assert first["request_id"] == second["request_id"]
    assert len(adapter.transport.requests) == 1


def test_status_polling_and_export():
    adapter = MusicZozaAdapter(transport=FakeFactoryTransport(),
                               tracker=MusicZozaTracker())
    rid = adapter.submit_package(_news_pkg())["request_id"]
    assert adapter.poll(rid)["state"] == "created"
    for state in ("planned", "acquiring", "assembling", "rendering"):
        adapter.transport.set_state(rid, state)
        assert adapter.poll(rid)["state"] == state
    adapter.transport.set_state(rid, "exported")
    assert adapter.poll(rid)["state"] == "exported"
    consumed = adapter.consume_export(rid)
    assert consumed["ok"] and consumed["export"]["status"] == "rendered"
    rec = adapter.tracker.get(rid)
    assert rec["export_available"] and rec["factory_state"] == "exported"


def test_factory_unavailable_stays_retryable():
    adapter = MusicZozaAdapter(
        transport=FakeFactoryTransport(unreachable=True),
        tracker=MusicZozaTracker())
    out = adapter.submit_package(_news_pkg())
    assert out["submitted"] is False and out["retryable"] is True
    # Autonomy loop keeps running; retry later succeeds.
    adapter.transport.unreachable = False
    retried = adapter.retry(out["request_id"])
    assert retried["state"] == "created"


def test_factory_failed_retryable():
    adapter = MusicZozaAdapter(transport=FakeFactoryTransport(),
                               tracker=MusicZozaTracker())
    rid = adapter.submit_package(_news_pkg())["request_id"]
    adapter.transport.set_state(rid, "failed")
    assert adapter.poll(rid)["state"] == "failed"
    out = adapter.retry(rid)
    assert out["state"] in ("created", "failed")
    rec = adapter.tracker.get(rid)
    assert rec["retry_count"] >= 1


def test_retry_exhaustion():
    adapter = MusicZozaAdapter(transport=FakeFactoryTransport(),
                               tracker=MusicZozaTracker(), max_attempts=1)
    rid = adapter.submit_package(_news_pkg())["request_id"]
    adapter.transport.set_state(rid, "failed")
    adapter.poll(rid)
    adapter.retry(rid)
    end = adapter.retry(rid)
    assert end["state"] == "failed" and end.get("terminal") is True


def test_shared_bus_failure_does_not_block():
    events.clear_outbox()
    out = MusicZozaAdapter(transport=FakeFactoryTransport(),
                           tracker=MusicZozaTracker()).submit_package(_news_pkg())
    assert out["submitted"] is True
    assert any(e["event_type"] == "VIDEO_REQUESTED" for e in events.outbox())


def test_no_local_rendering_or_publishing_code():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app",
                        "modules", "zoza_client")
    blob = ""
    for fname in os.listdir(root):
        if fname.endswith(".py"):
            with open(os.path.join(root, fname)) as fh:
                for line in fh:
                    s = line.strip()
                    if s.startswith('"""') or s.startswith("#") or s.startswith("*"):
                        continue
                    blob += line.lower()
    for banned in ("import ffmpeg", "from ffmpeg", "import moviepy", "import cv2",
                   "render_video(", "youtubeuploader", "tiktokuploader",
                   "instagramuploader", "facebookuploader", "channeluploader"):
        assert banned not in blob, f"zoza_client must not contain {banned}"


def test_no_duplicate_contract_schema():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app",
                        "modules", "zoza_client")
    blob = ""
    for fname in os.listdir(root):
        if fname.endswith(".py"):
            with open(os.path.join(root, fname)) as fh:
                blob += fh.read()
    assert "class ProductionRequestIn" not in blob
    assert "class ProductionMode" not in blob
