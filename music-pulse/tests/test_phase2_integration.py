"""Phase 2 integration: API endpoints, executive dashboard, Telegram commands."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(db, monkeypatch):
    """TestClient with get_db overridden to the isolated sqlite session."""
    from app.main import create_app
    from app.core.database import get_db
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c


def test_market_endpoints(client):
    r = client.post("/api/v2/markets/record", json={"country": "US", "title": "Hit",
                                                    "artist": "A", "score": 80.0})
    assert r.status_code == 200
    assert client.get("/api/v2/markets/rankings", params={"country": "US"}).status_code == 200
    assert "fastest" in client.get("/api/v2/markets/fastest").json()
    assert "comparison" in client.get("/api/v2/markets/compare", params={"title": "Hit"}).json()
    assert "migration" in client.get("/api/v2/markets/migration").json()
    assert client.post("/api/v2/markets/record", json={"country": "XX", "title": "X"}).status_code in (400, 422, 500)


def test_timezone_endpoints(client):
    assert "times" in client.get("/api/v2/timezone/best", params={"country": "DE"}).json()
    assert "heatmap" in client.get("/api/v2/timezone/heatmap").json()


def test_profitability_discovery_endpoints(client):
    assert client.post("/api/v2/profitability/record", json={"genre": "Pop", "views": 500}).status_code == 200
    assert "profitability" in client.get("/api/v2/profitability", params={"genre": "Pop"}).json()
    assert "leaderboard" in client.get("/api/v2/profitability/leaderboard").json()
    aid = client.post("/api/v2/discovery/artists", json={"artist": "Nova", "velocity": 1.2}).json()["id"]
    assert "artists" in client.get("/api/v2/discovery").json()
    assert client.post(f"/api/v2/discovery/watchlist/{aid}").status_code == 200
    assert "predictions" in client.get("/api/v2/discovery/breakout").json()


def test_sponsor_revenue_competitor_endpoints(client):
    sid = client.post("/api/v2/sponsors", json={"name": "Acme"}).json()["id"]
    cid = client.post("/api/v2/sponsors/campaigns",
                      json={"sponsor_id": sid, "name": "Push", "package": "newsletter"}).json()["id"]
    assert client.post(f"/api/v2/sponsors/campaigns/{cid}/revenue", params={"amount": 100}).status_code == 200
    assert "performance" in client.get("/api/v2/sponsors/performance").json()
    assert "sponsors" in client.get("/api/v2/sponsors").json()
    assert client.post("/api/v2/revenue", json={"source_type": "platform", "amount": 50}).status_code == 200
    s = client.get("/api/v2/revenue/summary").json()
    assert {"total", "mrr", "by_country"} <= set(s)
    assert "forecast" in client.get("/api/v2/revenue/forecast").json()
    assert client.post("/api/v2/competitors", json={"competitor": "Billboard", "topics": ["x"]}).status_code == 200
    g = client.get("/api/v2/competitors/gaps").json()
    assert {"gaps", "weaknesses", "opportunities"} <= set(g)


def test_openapi_lists_phase2(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert any(p.startswith("/api/v2/markets") for p in paths)
    assert any(p.startswith("/api/v2/revenue") for p in paths)


def test_executive_dashboard(client):
    r = client.get("/admin/executive")
    assert r.status_code == 200 and "Executive" in r.text


def test_phase2_telegram_commands_registered():
    from app.bot import telegram as t
    import inspect
    for cmd in ["markets", "profitability", "discover", "revenue", "sponsors", "competitors"]:
        fn = getattr(t, cmd)
        src = inspect.getsource(fn)
        assert "admin" in src.lower() or "_admin_only" in src or "admin_ids" in src


def test_telegram_admin_guard_blocks_non_admin(monkeypatch):
    import asyncio
    from app.bot import telegram as t
    from app.core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("TELEGRAM_ADMIN_IDS", "123")
    get_settings.cache_clear()

    class Msg:
        def __init__(self): self.replies = []
        async def reply_text(self, text): self.replies.append(text)
    class User:
        id = 999
    class Update:
        message = Msg()
        effective_user = User()
    class Ctx: pass
    asyncio.run(t.markets(Update(), Ctx()))
    assert Update.message.replies and "Admin only" in Update.message.replies[0]
    get_settings.cache_clear()
