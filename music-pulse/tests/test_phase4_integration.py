"""Phase 4 integration: v4 API, network dashboard, exec Telegram, v4 loop."""
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


def test_v4_acquisition_network_assets(client):
    assert client.post("/api/v4/acquisition/snapshot",
                       json={"channel": "social", "followers": 100}).status_code == 200
    assert client.post("/api/v4/acquisition/event",
                       json={"event_type": "visit", "count": 500}).status_code == 200
    rep = client.get("/api/v4/acquisition/report").json()
    assert {"report", "recommendations", "forecast"} <= set(rep)
    assert client.post("/api/v4/network/nodes",
                       json={"name": "MP Test", "kind": "brand"}).status_code == 200
    net = client.get("/api/v4/network").json()
    assert len(net["nodes"]) >= 7 and "plan" in net
    assert client.post("/api/v4/assets",
                       json={"name": "a.com", "kind": "website", "revenue": 100}).status_code == 200
    assert "valuation" in client.get("/api/v4/assets").json()


def test_v4_prediction_breakouts(client):
    assert client.post("/api/v4/prediction/song",
                       params={"subject": "Hit", "horizon_days": 7}).status_code == 200
    assert "forecasts" in client.get("/api/v4/prediction/report").json()
    assert client.post("/api/v4/prediction/mood", params={"subject": "x"}).status_code == 400
    assert "alerts" in client.post("/api/v4/breakouts/scan").json()
    assert "recommendations" in client.get("/api/v4/breakouts").json()


def test_v4_monetization_forecast_products(client):
    sid = client.post("/api/v2/sponsors", json={"name": "Acme4"}).json()["id"]
    m = client.get("/api/v4/monetization/match",
                   params={"genre": "Pop", "sponsor_id": sid}).json()
    assert {"matches", "pricing", "affiliates", "inventory", "allocation"} <= set(m)
    assert client.post("/api/v4/monetization/rules",
                       json={"name": "r1", "rule_type": "pricing"}).status_code == 200
    rex = client.get("/api/v4/revenue-execution").json()
    assert {"planned", "active", "utilization", "forecast"} <= set(rex)
    assert "projection" in client.post("/api/v4/forecasting",
                                     params={"scope": "revenue", "horizon": "quarterly"}).json()
    assert "forecast" in client.get("/api/v4/forecasting").json()
    pid = client.post("/api/v4/products",
                      json={"name": "Report", "kind": "report", "price": 29}).json()["id"]
    assert client.post(f"/api/v4/products/{pid}/sale", params={"amount": 29}).status_code == 200
    assert "totals" in client.get("/api/v4/products").json()


def test_v4_loop_openapi_dashboard(client):
    out = client.post("/api/v3/autonomy/cycle").json()
    assert out["status"] in ("completed", "failed", "skipped")
    v4 = client.post("/api/v4/autonomy/cycle-v4").json()
    assert v4["status"] in ("completed", "failed", "skipped")
    if v4["status"] != "skipped":
        assert len(v4["stages"]) == 11
    paths = client.get("/openapi.json").json()["paths"]
    for prefix in ("/api/v4/acquisition", "/api/v4/network", "/api/v4/assets",
                   "/api/v4/prediction", "/api/v4/breakouts", "/api/v4/monetization",
                   "/api/v4/revenue-execution", "/api/v4/forecasting", "/api/v4/products"):
        assert any(p.startswith(prefix) for p in paths), prefix
    r = client.get("/admin/network")
    assert r.status_code == 200 and "Network" in r.text


def test_phase4_telegram_commands():
    from app.bot import telegram as t
    for cmd in ["growth", "predict", "breakouts", "assets",
                "network", "monetize", "forecast", "products"]:
        assert callable(getattr(t, cmd)), cmd
