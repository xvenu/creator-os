"""Performance feedback loop: ingest video results, update the brain."""
from __future__ import annotations

from app.core.audit import audit

KINDS = ("views", "watch_time", "revenue", "ctr", "retention", "growth")


def ingest(db, job_id: int, kind: str, value: float, actor: str = "feedback"):
    from app.models.phase6 import FeedbackEvent
    if kind not in KINDS:
        raise ValueError(f"kind must be {KINDS}")
    row = FeedbackEvent(job_id=job_id, kind=kind, value=value)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "feedback.received", "feedback", row.id,
          {"job": job_id, "kind": kind})
    return row


def apply_feedback(db, actor: str = "feedback") -> dict:
    """Update opportunity scores, forecasts, predictions, monetization."""
    from app.models.phase6 import FeedbackEvent
    from app.modules.video_intelligence.engine import feed_back
    from app.modules.memory.engine import store
    events = db.query(FeedbackEvent).count()
    learned = feed_back(db, actor)
    rev_total = sum(float(e.value or 0) for e in
                    db.query(FeedbackEvent).filter(FeedbackEvent.kind == "revenue").all())
    if rev_total:
        from app.modules.revenue.engine import record_revenue
        record_revenue(db, "platform", rev_total, platform="zoza", actor=actor)
    store(db, "lesson", f"feedback applied over {events} events",
          str(learned), actor=actor)
    audit(db, actor, "feedback.applied", "feedback", "", {"events": events})
    return {"events": events, "learnings": learned, "revenue_attributed": rev_total}
