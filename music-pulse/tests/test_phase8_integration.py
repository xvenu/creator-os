"""Phase 8 integration: v8 Creator API + distribution endpoints."""
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


def test_v8_creator_surface(client):
    assert client.post("/api/v8/creator/notifications",
                       json={"event": "system", "message": "refactor live"}).status_code == 200
    assert "notifications" in client.get("/api/v8/creator/notifications").json()
    tg = client.get("/api/v8/creator/telegram").json()
    assert tg["owner"] == "creator-os" and tg["pulse_bot"] == "deprecated"
    assert "registered" in client.get("/api/v8/creator/network").json()
    assert client.post("/api/v8/creator/register",
                       params={"name": "music-pulse"}).status_code == 200
    fac = client.get("/api/v8/creator/factories").json()
    assert "factories" in fac and "route_preview" in fac
    assert "assets" in client.get("/api/v8/creator/assets").json()


def test_v8_distribution_flow(client):
    pid = client.post("/api/v6/packages",
                      json={"type": "news", "title": "Dist Story"}).json()["id"]
    jid = client.post(f"/api/v6/zoza/dispatch/{pid}").json()["job_id"]
    asset = client.post(f"/api/v8/zoza/export/{jid}",
                        params={"video_path": "/v.mp4",
                                "thumbnail_path": "/t.jpg"}).json()
    assert asset["asset_id"].startswith("asset-")
    pub = client.post(f"/api/v8/distribution/publish/{asset['asset_id']}").json()
    assert pub["sent"] == 1
    tr = client.post(f"/api/v8/distribution/track/{asset['asset_id']}",
                     params={"views": 500, "revenue": 2.5}).json()
    assert tr == {"asset_id": asset["asset_id"], "views": 500, "revenue": 2.5}
    paths = client.get("/openapi.json").json()["paths"]
    assert any(p.startswith("/api/v8/creator/") for p in paths)
