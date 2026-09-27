"""Factory auth: per-pulse scoping + negative tests (401/403, admin pass)."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.database import get_session_factory, init_db, reset_engine


@pytest.fixture(scope="module")
def auth_client(tmp_path_factory):
    d = tmp_path_factory.mktemp("auth")
    saved = {k: os.environ.get(k) for k in
             ("PULSE_TOKEN_MUSIC", "PULSE_TOKEN_FOOTBALL", "FACTORY_ADMIN_TOKEN",
              "DATABASE_URL", "OUTPUT_DIR")}
    os.environ["PULSE_TOKEN_MUSIC"] = "tok-music-123"
    os.environ["PULSE_TOKEN_FOOTBALL"] = "tok-foot-456"
    os.environ["FACTORY_ADMIN_TOKEN"] = "tok-admin-789"
    os.environ["DATABASE_URL"] = f"sqlite:///{d}/auth.db"
    os.environ["OUTPUT_DIR"] = str(d / "output")
    (d / "output").mkdir(exist_ok=True)
    from app.core.config import get_settings
    get_settings.cache_clear()
    reset_engine()
    init_db()
    from app.main import create_app
    app = create_app()

    def _override():
        db = get_session_factory()()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    for var, val in saved.items():
        if val is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = val
    get_settings.cache_clear()
    reset_engine()


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _req(rid, goal="Auth story. Second beat."):
    return {"request_id": rid, "pulse": "music-pulse", "goal": goal,
            "style": "news", "length_seconds": 20, "production_mode": "REALITY_FIRST"}


def test_unknown_token_401(auth_client):
    assert auth_client.get("/api/v1/capacity").status_code == 200  # open
    r = auth_client.post("/api/v1/requests", json=_req("a-1"),
                         headers=_h("nope"))
    assert r.status_code == 401


def test_owner_ok_cross_pulse_403_admin_ok(auth_client):
    m, f, a = _h("tok-music-123"), _h("tok-foot-456"), _h("tok-admin-789")
    assert auth_client.post("/api/v1/requests", json=_req("m-own-1"), headers=m).status_code == 200
    # football token cannot read music's request
    assert auth_client.get("/api/v1/requests/m-own-1", headers=f).status_code == 403
    # music token cannot spoof pulse field: creation forces owner pulse
    body = _req("m-own-2")
    body["pulse"] = "football-pulse"
    created = auth_client.post("/api/v1/requests", json=body, headers=m).json()
    assert created["pulse"] == "music-pulse"
    # admin reads everything
    assert auth_client.get("/api/v1/requests/m-own-1", headers=a).status_code == 200
    # music cannot execute football-owned row
    fb = dict(_req("f-own-1"), pulse="x")
    assert auth_client.post("/api/v1/requests", json=fb, headers=f).status_code == 200
    assert auth_client.post("/api/v1/requests/f-own-1/execute", headers=m).status_code == 403


def test_no_credential_leak_in_auth_errors(auth_client):
    r = auth_client.post("/api/v1/requests", json=_req("x-1"), headers=_h("tok-music-123-WRONG"))
    assert r.status_code == 401
    assert "tok-music-123" not in r.text
