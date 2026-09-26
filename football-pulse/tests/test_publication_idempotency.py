"""Football publication idempotency + retry + webhook receipt (sync sqlite)."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def sdb():
    from app.db.base import Base
    import app.db.models  # noqa: F401
    import app.db.models.phase6  # noqa: F401
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine)
    s = S()
    yield s
    s.close()


def test_duplicate_queue_reuses_row(sdb):
    from app.services.publication_service import queue_delivery
    r1, created1 = queue_delivery(sdb, "pkg-1", "webhook", "@foot", "v1")
    r2, created2 = queue_delivery(sdb, "pkg-1", "webhook", "@foot", "v1")
    assert created1 is True and created2 is False
    assert r1.id == r2.id


def test_new_version_new_row_and_retry_sends_once(sdb):
    from app.db.models.phase6 import PublicationDelivery
    from app.services.publication_service import deliver_due, queue_delivery
    queue_delivery(sdb, "pkg-2", "webhook", "@foot", "v1")
    rb, _ = queue_delivery(sdb, "pkg-2", "webhook", "@foot", "v2")
    calls = {"n": 0}

    def flaky(row):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        return {"remote_id": "wh-9", "status": "published"}

    out = deliver_due(sdb, sender=flaky)
    assert out["failed"] == 1
    rows = sdb.query(PublicationDelivery).all()
    for r in rows:
        import datetime as dt
        r.scheduled_at = dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc)
    sdb.commit()
    out = deliver_due(sdb, sender=flaky)
    assert out["sent"] >= 1
    assert calls["n"] == 3  # fail once, then each intent sent exactly once


def test_webhook_real_http_receipt(sdb, monkeypatch):
    from app.services.publication_service import deliver_due, queue_delivery

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            self.rfile.read(n)
            body = json.dumps({"id": "remote-123"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("FOOTBALL_WEBHOOK_URL", f"http://127.0.0.1:{srv.server_port}/hook")
    queue_delivery(sdb, "pkg-web", "webhook", "@foot", "v1")
    out = deliver_due(sdb)
    srv.shutdown()
    assert out["sent"] == 1
    from app.db.models.phase6 import PublicationDelivery
    row = sdb.query(PublicationDelivery).filter_by(package_ref="pkg-web").one()
    assert row.remote_id == "remote-123" and row.status == "sent"
