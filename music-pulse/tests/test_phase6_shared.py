"""Shared layer: event bus persistence/replay, knowledge, orchestrator."""
import os

import app.core.shared  # noqa: F401 — puts creator-os root on sys.path
from shared import event_bus, knowledge
from shared import orchestrator as orch


def test_bus_pub_sub_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(event_bus, "_DB", str(tmp_path / "bus.db"))
    got = []
    event_bus.subscribe("TREND_FOUND", got.append)
    e1 = event_bus.publish("TREND_FOUND", {"topic": "Nova"}, source_pulse="music-pulse")
    assert e1["id"] > 0 and got and got[0]["payload"] == {"topic": "Nova"}
    event_bus.register_poller("zoza-video-factory", "TREND_FOUND")
    event_bus.publish("TREND_FOUND", {"topic": "X"})
    pend = event_bus.pending("zoza-video-factory", "TREND_FOUND")
    assert len(pend) == 2  # both events since poller registered after? no—
    # poller cursor starts at 0 → sees all; second poll sees none
    assert event_bus.pending("zoza-video-factory", "TREND_FOUND") == []
    rep = event_bus.replay(e1["id"] - 1)
    assert any(e["id"] == e1["id"] for e in rep)
    import pytest
    with pytest.raises(ValueError):
        event_bus.publish("NOPE", {})


def test_knowledge_crud(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge, "_DB", str(tmp_path / "k.db"))
    knowledge.put("artist", "Nova", {"genre": "Pop"})
    assert knowledge.get("artist", "Nova")["value"] == {"genre": "Pop"}
    assert knowledge.get("artist", "Nobody") is None
    assert knowledge.search("artist", "Nov")[0]["key"] == "Nova"
    import pytest
    with pytest.raises(ValueError):
        knowledge.put("alien", "x", {})


def test_orchestrator(tmp_path, monkeypatch):
    monkeypatch.setattr(orch, "_DB", str(tmp_path / "o.db"))
    orch.heartbeat("music-pulse", "healthy", load=0.2)
    orch.heartbeat("zoza-video-factory", "healthy", load=0.8)
    h = orch.health()
    assert {p["pulse"] for p in h} == {"music-pulse", "zoza-video-factory"}
    plan = orch.distribute([{"w": 1}, {"w": 2}])
    assert sum(len(v) for v in plan.values()) == 2
    rep = orch.network_report()
    assert rep["healthy"] == 2 and rep["total_queue"] == 0
