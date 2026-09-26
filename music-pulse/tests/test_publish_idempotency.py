"""Publishing idempotency: same intent → same job; retry reuses; new version → new job."""
from __future__ import annotations


def _content(db):
    from app.models.models import ContentItem
    c = ContentItem(kind="short", title="T", body="B", status="draft")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_duplicate_queue_returns_same_job(db):
    from app.modules.publisher.engine import queue_post
    c = _content(db)
    j1 = queue_post(db, c.id, "webhook", target_account="@music", content_version="v1")
    j2 = queue_post(db, c.id, "webhook", target_account="@music", content_version="v1")
    assert j1.id == j2.id
    assert j1.idempotency_key == j2.idempotency_key != ""


def test_new_version_mints_new_job_and_retry_reuses_intent(db):
    from app.models.models import PublishJob
    from app.modules.publisher.engine import publish_due_jobs, queue_post
    c = _content(db)
    j1 = queue_post(db, c.id, "webhook", target_account="@music", content_version="v1")
    jv2 = queue_post(db, c.id, "webhook", target_account="@music", content_version="v2")
    assert jv2.id != j1.id
    # Transient failure keeps the same intent; retry sends once.
    calls = {"n": 0}

    def flaky(job, content):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom (retryable)")
        return {"remote_id": "wh-1", "status": "published"}

    out = publish_due_jobs(db, sender=flaky)
    assert out["failed"] == 1
    # Immediate retry is in backoff; force due and retry same intent.
    row = db.get(PublishJob, j1.id)
    from datetime import datetime
    row.scheduled_at = datetime(2000, 1, 1)
    db.commit()
    out = publish_due_jobs(db, sender=flaky)
    assert out["sent"] >= 1
    row = db.get(PublishJob, j1.id)
    assert row.status == "sent" and row.remote_id == "wh-1"
    assert db.query(PublishJob).filter_by(idempotency_key=j1.idempotency_key).count() == 1


def test_no_duplicate_send_after_sent(db):
    from app.models.models import PublishJob
    from app.modules.publisher.engine import publish_due_jobs, queue_post
    c = _content(db)
    j = queue_post(db, c.id, "log")
    out = publish_due_jobs(db)
    assert out["sent"] == 1
    out = publish_due_jobs(db)
    assert out["sent"] == 0  # same intent never re-sends
    assert db.get(PublishJob, j.id).attempts == 1


def test_webhook_real_http_receipt(db, monkeypatch):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from app.modules.publisher.engine import publish_due_jobs, queue_post

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            self.rfile.read(n)
            body = json.dumps({"id": "m-remote-7"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("MUSIC_WEBHOOK_URL", f"http://127.0.0.1:{srv.server_port}/hook")
    c = _content(db)
    j = queue_post(db, c.id, "webhook", target_account="@music")
    out = publish_due_jobs(db)
    srv.shutdown()
    assert out["sent"] == 1
    from app.models.models import PublishJob
    assert db.get(PublishJob, j.id).remote_id == "m-remote-7"
