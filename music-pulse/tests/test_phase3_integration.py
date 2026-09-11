"""Phase 3 integration: v3 API, autonomy dashboard, exec Telegram, policy gate."""
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


def test_v3_executive_strategy(client):
    assert client.post("/api/v3/executive/run").status_code == 200
    assert "revenue" in client.get("/api/v3/executive/analyze").json()
    gid = client.post("/api/v3/executive/goals",
                      json={"title": "MRR 10k", "category": "revenue", "target": 10000}).json()["id"]
    assert any(g["id"] == gid for g in client.get("/api/v3/executive/goals").json()["goals"])
    assert client.post("/api/v3/strategy/generate", params={"horizon": "weekly"}).status_code == 200
    assert client.get("/api/v3/strategy/latest").status_code == 200


def test_v3_memory_opps_decisions(client):
    assert client.post("/api/v3/memory", json={"kind": "lesson", "title": "Pop wins"}).status_code == 200
    assert "lessons" in client.get("/api/v3/memory", params={"query": "Pop"}).json()
    assert "scored" in client.post("/api/v3/opportunities/score").json()
    assert "allocation" in client.get("/api/v3/opportunities").json()
    did = client.post("/api/v3/decisions", json={
        "question": "Hip-Hop or Pop?",
        "options": [{"name": "Hip-Hop", "signals": {"profit": 10}},
                    {"name": "Pop", "signals": {"profit": 50}}]}).json()["id"]
    assert client.get("/api/v3/decisions").json()["decisions"][0]["chosen"] == "Pop"
    assert client.post(f"/api/v3/decisions/{did}/outcome", params={"outcome": "success"}).status_code == 200


def test_v3_autonomy_warroom(client):
    out = client.post("/api/v3/autonomy/cycle").json()
    assert out["status"] in ("completed", "failed", "skipped")
    assert "cycles" in client.get("/api/v3/autonomy/cycles").json()
    assert "feed" in client.get("/api/v3/autonomy/feed").json()
    assert "events" in client.get("/api/v3/autonomy/policy").json()
    assert "frequency" in client.get("/api/v3/warroom/briefing").json()
    assert "strategies" in client.get("/api/v3/warroom/attack").json()
    assert "recommendations" in client.post("/api/v3/revenue-optimizer/run").json()
    assert "directives" in client.get("/api/v3/director/directives").json()
    # safety endpoints
    assert client.post("/api/v3/autonomy/stop", params={"reason": "test"}).json()["stopped"] is True
    assert client.post("/api/v3/autonomy/cycle").json()["status"] == "skipped"
    assert client.post("/api/v3/autonomy/override", params={"action": "resume"}).json()["running"] is True


def test_v3_openapi_and_dashboard(client):
    paths = client.get("/openapi.json").json()["paths"]
    for prefix in ("/api/v3/executive", "/api/v3/strategy", "/api/v3/memory",
                   "/api/v3/opportunities", "/api/v3/decisions",
                   "/api/v3/autonomy", "/api/v3/warroom"):
        assert any(p.startswith(prefix) for p in paths), prefix
    r = client.get("/admin/autonomy")
    assert r.status_code == 200 and "Autonomy" in r.text


def test_policy_gate_blocks_publishing(db):
    from app.modules.content.engine import generate_content, persist_content
    from app.modules.publisher.engine import queue_post, publish_due_jobs
    c = persist_content(db, generate_content("news", "Clean Song"))
    c.title, c.body = "Election rigged", "vote for X at campaign rally"
    db.commit()
    queue_post(db, c.id, "log")
    summary = publish_due_jobs(db)
    assert summary["failed"] == 1 and summary["sent"] == 0


def test_exec_telegram_commands_exist():
    from app.bot import telegram as t
    for cmd in ["executive", "strategy", "memory", "opportunities",
                "decisions_cmd", "autonomy", "warroom"]:
        assert callable(getattr(t, cmd)), cmd
