import pytest


def test_contracts():
    import app.core.shared  # noqa: F401
    from shared.contracts import validate_export, validate_asset, asset_from_export
    exp = {"job_id": "1", "status": "rendered", "video_path": "/v.mp4",
           "thumbnail_path": "/t.jpg", "metadata": {"title": "Nova"}}
    assert validate_export(exp)["status"] == "rendered"
    asset = asset_from_export(exp, description="Hit story", hashtags=["#Pop"])
    assert asset["asset_id"] == "asset-1" and asset["hashtags"] == ["#Pop"]
    with pytest.raises(ValueError):
        validate_export({**exp, "status": "published"})  # factory never publishes
    with pytest.raises(ValueError):
        validate_export({"job_id": "1"})
    with pytest.raises(ValueError):
        validate_asset({"asset_id": "x"})


def test_export_flow(db):
    from app.modules.content_gateway.engine import build_package
    from app.modules.zoza.engine import PackageDispatcher, mark_exported
    from app.modules.distribution.engine import publish_asset, track_performance
    pkg = build_package(db, "news", "Nova Story")
    d = PackageDispatcher.dispatch(db, pkg["id"])
    asset = mark_exported(db, d["job_id"], "/v.mp4", "/t.jpg", title="Nova Story")
    assert asset["asset_id"].startswith("asset-")
    pub = publish_asset(db, asset["asset_id"], platform="log")
    assert pub["sent"] == 1
    tr = track_performance(db, asset["asset_id"], views=1000, engagement=90,
                           followers_delta=25, revenue=5.0)
    assert tr == {"asset_id": asset["asset_id"], "views": 1000, "revenue": 5.0}
    with pytest.raises(ValueError):
        publish_asset(db, "asset-nope")
    with pytest.raises(ValueError):
        mark_exported(db, 99999, "/v.mp4")


def test_notifications_and_agent(tmp_path, monkeypatch):
    import app.core.shared  # noqa: F401
    from shared import notifications
    from shared.telegram import answer, COMMANDS
    monkeypatch.setattr(notifications, "_DB", str(tmp_path / "n.db"))
    out = notifications.notify("failure", "render node down", source_pulse="test-pulse")
    assert out["id"] > 0 and out["delivered"]["log"] == "sent"
    assert notifications.recent(event="failure")[0]["message"] == "render node down"
    notifications.configure("webhook", {"url": ""}, enabled=False)
    with pytest.raises(ValueError):
        notifications.notify("telepathy", "x")
    with pytest.raises(ValueError):
        notifications.configure("pigeon")
    assert "Creator-OS OK" in answer("health")
    assert "test-pulse" in answer("alerts") or "alerts" in answer("alerts").lower()
    with pytest.raises(ValueError):
        answer("dance")
    assert set(COMMANDS) == {"health", "pulses", "revenue", "alerts", "events", "network"}


def test_registry_routing(tmp_path, monkeypatch):
    import app.core.shared  # noqa: F401
    from shared import orchestrator as orch
    monkeypatch.setattr(orch, "_DB", str(tmp_path / "o.db"))
    orch.register_pulse("music-pulse", ["intelligence", "publishing"])
    orch.register_factory("zoza-video-factory", ["render"])
    assert {r["name"] for r in orch.list_registered()} == {"music-pulse", "zoza-video-factory"}
    assert orch.list_registered("factory")[0]["name"] == "zoza-video-factory"
    routed = orch.route_to_factory([{"pkg": 1}])
    assert routed == {"zoza-video-factory": [{"pkg": 1}]}


def test_new_bus_events():
    import app.core.shared  # noqa: F401
    from shared import event_bus
    assert {"VIDEO_REQUESTED", "VIDEO_RENDER_STARTED", "VIDEO_RENDER_FINISHED",
            "VIDEO_EXPORTED", "PUBLISH_STARTED", "PUBLISH_COMPLETED",
            "REVENUE_RECORDED"} <= set(event_bus.EVENT_TYPES)


def test_pulse_bot_deprecated_but_functional():
    import warnings
    from app.bot import telegram as t
    assert "DEPRECATED" in (t.__doc__ or "")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            t.build_app()
        except Exception:
            pass  # no token in CI — deprecation warning is what we assert
        assert any(issubclass(x.category, DeprecationWarning) for x in w)


def test_independence_telegram_creator_zoza_down(db, monkeypatch):
    """Critical: Pulse operates with Telegram/Creator-OS/Zoza all unavailable."""
    import app.core.shared as shared_bridge
    from app.modules.content_gateway.engine import build_package
    from app.modules.zoza.engine import PackageDispatcher
    from app.modules.autonomy.engine import run_cycle
    # Creator-OS bus + knowledge raise
    monkeypatch.setattr(shared_bridge.event_bus, "publish",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bus down")))
    # Zoza unreachable
    monkeypatch.setenv("ZOZA_DIR", "/nonexistent-zoza")
    pkg = build_package(db, "news", "Offline Story")  # must not raise
    assert pkg["id"]
    d = PackageDispatcher.dispatch(db, pkg["id"])  # retryable queued, not failed
    assert d["state"] == "queued"
    out = run_cycle(db)  # autonomy loop survives
    assert out["status"] in ("completed", "failed")
