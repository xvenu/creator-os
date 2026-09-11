"""Phase 6 integration: v6 API, creator dashboard, exec Telegram, pipeline."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(db):
    from app.main import create_app
    from app.core.database import get_db
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c


def _seed(db):
    from app.modules.market_intelligence.engine import record_country_trend
    from app.modules.profitability.engine import record_genre_analytic
    record_country_trend(db, "US", "Viral Hit", artist="Nova", score=150.0, genre="Pop")
    record_genre_analytic(db, "Pop", "US", views=3000, engagement=600, posts=8)


def test_v6_packages_formats(client, db):
    _seed(db)
    pid = client.post("/api/v6/packages",
                      json={"type": "news", "title": "Nova Explodes"}).json()["id"]
    assert "script" in client.get(f"/api/v6/packages/{pid}/export").json()
    assert client.post(f"/api/v6/packages/{pid}/queue").status_code == 200
    assert "packages" in client.get("/api/v6/packages").json()
    p2 = client.post("/api/v6/packages/from-opportunity",
                     params={"topic": "Viral Hit"}).json()
    assert p2["priority_score"] > 0
    assert "opportunities" in client.get("/api/v6/packages/opportunities/top").json()
    rec = client.get("/api/v6/packages/formats/recommend",
                     params={"topic": "Viral Hit"}).json()
    assert rec["recommendation"]["format"] in ("shorts", "reels", "tiktok", "longform",
                                               "documentary", "news", "listicle",
                                               "deepdive", "biography")


def test_v6_zoza_pipeline_videos(client, db):
    _seed(db)
    ping = client.get("/api/v6/zoza/ping").json()
    assert ping["factory"] == "zoza-video-factory" and "reachable" in ping
    pid = client.post("/api/v6/packages",
                      json={"type": "review", "title": "Nova Review"}).json()["id"]
    d = client.post(f"/api/v6/zoza/dispatch/{pid}").json()
    assert d["state"] in ("queued", "rendering", "failed")
    jid = d["job_id"]
    assert client.post(f"/api/v6/zoza/render/{jid}",
                       params={"video_url": "http://v/1.mp4"}).json()["state"] == "rendered"
    assert client.post(f"/api/v6/zoza/publish/{jid}",
                       params={"platform": "youtube"}).json()["state"] == "published"
    assert "jobs" in client.get("/api/v6/zoza/jobs").json()
    assert client.post("/api/v6/videos/metrics",
                       json={"job_id": jid, "views": 9000, "revenue": 18.0}).status_code == 200
    intel = client.get("/api/v6/videos/intelligence").json()
    assert {"formats", "markets", "applied"} <= set(intel)
    pipe = client.post("/api/v6/pipeline/run", params={"limit": 2}).json()
    assert pipe["status"] in ("completed", "failed", "disabled")


def test_v6_events_knowledge_network_feedback(client):
    assert client.post("/api/v6/events", params={"event_type": "TREND_FOUND"}).status_code == 200
    assert "events" in client.get("/api/v6/events").json()
    assert "events" in client.get("/api/v6/events/replay").json()
    assert client.post("/api/v6/knowledge",
                       params={"domain": "artist", "key": "Nova"},
                       json={}).status_code in (200, 422)
    assert "results" in client.get("/api/v6/knowledge",
                                   params={"domain": "artist"}).json()
    assert "pulses" in client.get("/api/v6/network/health").json()
    assert client.post("/api/v6/feedback",
                       json={"job_id": 1, "kind": "views", "value": 100}).status_code == 200
    assert "learnings" in client.post("/api/v6/feedback/apply").json()


def test_v6_openapi_dashboard_bot(client):
    paths = client.get("/openapi.json").json()["paths"]
    for prefix in ("/api/v6/packages", "/api/v6/zoza", "/api/v6/videos",
                   "/api/v6/events", "/api/v6/feedback", "/api/v6/network",
                   "/api/v6/knowledge"):
        assert any(p.startswith(prefix) for p in paths), prefix
    r = client.get("/admin/creator")
    assert r.status_code == 200 and "Creator-OS" in r.text
    from app.bot import telegram as t
    for cmd in ["zoza", "packages", "videos", "pipeline", "events",
                "network_cmd", "knowledge_cmd", "feedback"]:
        assert callable(getattr(t, cmd)), cmd
