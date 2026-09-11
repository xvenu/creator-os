"""Phase 7 integration: v7 API, reality dashboard, graph, exec Telegram."""
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


def test_v7_reality_verify(client):
    assert client.post("/api/v7/reality/discover").json()["total"] >= 8
    assert client.post("/api/v7/reality/evidence",
                       params={"claim": "Nova #1"}).status_code == 200
    rep = client.get("/api/v7/reality/report", params={"topic": "Nova #1"}).json()
    assert rep["reality_first"] is True
    v = client.post("/api/v7/verify",
                    params={"subject": "Nova #1", "trusted_hits": 2}).json()
    assert v["verdict"] == "verified"
    assert "verifications" in client.get("/api/v7/verify").json()
    d = client.get("/api/v7/executive/reality-decision",
                   params={"question": "Nova #1"}).json()
    assert d["tier"] == "verified_reality"


def test_v7_sources_assets_rights(client):
    sid = client.post("/api/v7/sources",
                      json={"name": "S1", "kind": "press", "official": True}).json()["id"]
    assert client.get("/api/v7/sources").json()["sources"][0]["official"] is True
    assert client.post(f"/api/v7/sources/{sid}/score",
                       params={"trust": 0.9, "authority": 0.8}).status_code == 200
    aid = client.post("/api/v7/assets",
                      json={"title": "Pic", "kind": "photo",
                            "attribution": "Label"}).json()["id"]
    assert client.get("/api/v7/assets").json()["assets"]
    assert client.post(f"/api/v7/assets/{aid}/rights",
                       params={"license": "editorial-use"}).status_code == 200
    assert client.get(f"/api/v7/assets/{aid}/rights").json()["status"] == "cleared"


def test_v7_artists_labels_newsroom_doc(client):
    assert client.post("/api/v7/artists",
                       json={"artist": "Nova", "momentum": 9.0}).status_code == 200
    assert client.get("/api/v7/artists").json()["artists"][0]["artist"] == "Nova"
    assert client.post("/api/v7/labels",
                       json={"label": "Label X", "kind": "major"}).status_code == 200
    assert client.get("/api/v7/labels").json()["labels"]
    r = client.post("/api/v7/newsroom",
                    json={"kind": "news", "title": "Nova #1", "body": "Charts.",
                          "sources": [{"trusted": True}] * 3}).json()
    assert r["verification"] == "verified"
    assert client.get("/api/v7/newsroom").json()["reports"]
    pid = client.post("/api/v7/documentary", params={"subject": "Nova"}).json()["id"]
    ship = client.post(f"/api/v7/documentary/{pid}/package").json()
    assert ship["type"] == "documentary" and "evidence" in ship


def test_v7_graph_openapi_dashboard_bot(client):
    assert client.post("/api/v7/knowledge/graph",
                       params={"domain": "artist_graph", "src": "Nova",
                               "rel": "signed_to", "dst": "Label X"}).status_code == 200
    g = client.get("/api/v7/knowledge/graph",
                   params={"domain": "artist_graph", "node": "Nova"}).json()
    assert g["neighbors"][0]["dst"] == "Label X" and "artist_graph" in g["stats"]
    paths = client.get("/openapi.json").json()["paths"]
    for prefix in ("/api/v7/reality", "/api/v7/sources", "/api/v7/assets",
                   "/api/v7/verify", "/api/v7/artists", "/api/v7/labels",
                   "/api/v7/newsroom", "/api/v7/documentary"):
        assert any(p.startswith(prefix) for p in paths), prefix
    r = client.get("/admin/reality")
    assert r.status_code == 200 and "Reality Center" in r.text
    from app.bot import telegram as t
    for cmd in ["reality", "sources", "assets_cmd", "verify", "artists",
                "labels", "newsroom", "documentary"]:
        assert callable(getattr(t, cmd)), cmd
