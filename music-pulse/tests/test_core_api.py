from app.core.plugins import PluginRegistry


def test_registry_and_audit(db):
    r = PluginRegistry()
    r.register_trend_provider("x", object())
    assert "x" in r.trend_providers
    called = []
    r.on("evt", lambda v: called.append(v))
    r.emit("evt", 1)
    assert called == [1]

    from app.core.audit import audit
    audit(db, "test", "thing.did", "widget", "1", {"k": "v"})
    audit(None, "test", "no-db-action")  # must not raise


def test_api_health():
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.core.database import init_db
    init_db()
    with TestClient(create_app()) as c:
        assert c.get("/health").json()["status"] == "ok"
        assert "MusicPulse" in c.get("/admin").text
