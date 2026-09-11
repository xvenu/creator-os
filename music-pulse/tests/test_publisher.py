from app.modules.content.engine import generate_content, persist_content
from app.modules.publisher.engine import queue_post, publish_due_jobs


def test_queue_and_publish_success(db):
    c = persist_content(db, generate_content("short", "Viral Song"))
    job = queue_post(db, c.id, "log")
    assert job.status == "queued"
    summary = publish_due_jobs(db)
    assert summary["sent"] == 1
    assert job.status == "sent"


def test_retry_backoff_on_failure(db):
    from app.core.plugins import registry
    c = persist_content(db, generate_content("news", "Flop Song"))
    registry.register_publisher("always-fail", lambda job, content: (_ for _ in ()).throw(RuntimeError("boom")))
    job = queue_post(db, c.id, "always-fail")
    summary = publish_due_jobs(db)
    assert summary["failed"] == 1
    assert job.attempts == 1 and job.status == "failed"
    del registry.publishers["always-fail"]
