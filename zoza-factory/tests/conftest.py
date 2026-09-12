"""Test fixtures: isolated sqlite file DB per session + TestClient with get_db override."""
from __future__ import annotations

import os

import pytest

# Set BEFORE importing app modules so get_settings() picks up the test DB.
_TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".test-tmp")
os.makedirs(_TEST_DIR, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR}/test-factory.db"
os.environ["ENVIRONMENT"] = "test"
os.environ["OUTPUT_DIR"] = os.path.join(_TEST_DIR, "output")

# Remove stale test DB so each run starts clean.
for _f in ("test-factory.db",):
    _p = os.path.join(_TEST_DIR, _f)
    if os.path.exists(_p):
        os.remove(_p)

from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import get_db  # noqa: E402
from app.core.database import get_session_factory, init_db, reset_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.modules.reality_assets import acquisition as assets_mod  # noqa: E402


@pytest.fixture(scope="session")
def client():
    reset_engine()
    init_db()
    db = get_session_factory()()
    try:
        assets_mod.seed_catalog(db)
    finally:
        db.close()

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


def make_request(**overrides) -> dict:
    base = {
        "request_id": "req-test-001",
        "pulse": "music-pulse",
        "goal": "Create a documentary about Burna Boy.",
        "style": "documentary",
        "length_seconds": 60,
        "urgency": "normal",
        "production_mode": "REALITY_FIRST",
        "ai_generation_allowed": False,
        "sources": [],
        "evidence": [],
        "voice_profile": "",
        "target_audience": "general",
        "priority": 50,
    }
    base.update(overrides)
    return base


REAL_SOURCES = [
    {"source": "official: Burna Boy press kit photo", "license": "official-use attribution-required",
     "trust_score": 0.9, "rights_status": "RESTRICTED", "kind": "real_photo",
     "category": "official_photo", "duration_seconds": 5.0},
    {"source": "documentary: concert footage archive", "license": "factory-licensed",
     "trust_score": 0.85, "rights_status": "CLEARED", "kind": "real_footage",
     "category": "documentary", "duration_seconds": 30.0},
]

REAL_EVIDENCE = [
    {"source": "verified: award ceremony record", "license": "public-domain",
     "trust_score": 0.8, "rights_status": "CLEARED", "kind": "public_domain",
     "category": "archive", "verified": True, "text": "Burna Boy won the Grammy in 2021."},
]
