"""Pulse-owned distribution: the Pulse publishes, tracks, learns. Zoza never publishes.

Flow: ExportedAsset (from Zoza export) → publish via platform publishers →
performance tracked (analytics/audience/revenue) → learnings fed back.
"""
from __future__ import annotations

from app.core.audit import audit


def publish_asset(db, asset_id: str, platform: str = "log", actor: str = "distribution") -> dict:
    """Publish an exported asset. Emits PUBLISH_STARTED/COMPLETED; fails open to audit."""
    from app.models.phase8 import ExportedAsset
    from app.modules.publisher.engine import queue_post, publish_due_jobs
    from app.modules.content.engine import generate_content, persist_content
    asset = db.get(ExportedAsset, asset_id)
    if asset is None:
        raise ValueError(f"asset {asset_id} not found")
    _emit("PUBLISH_STARTED", {"asset_id": asset_id, "platform": platform})
    content = generate_content("short", asset.title)
    row = persist_content(db, content, status="queued")
    job = queue_post(db, row.id, platform, delay_minutes=0, actor=actor)
    summary = publish_due_jobs(db)
    asset.published = True
    db.commit()
    _emit("PUBLISH_COMPLETED", {"asset_id": asset_id, "sent": summary["sent"]})
    audit(db, actor, "distribution.published", "asset", asset_id,
          {"platform": platform, "sent": summary["sent"]})
    return {"asset_id": asset_id, "job_id": job.id, "sent": summary["sent"]}


def track_performance(db, asset_id: str, views: int = 0, engagement: int = 0,
                      followers_delta: int = 0, revenue: float = 0.0,
                      actor: str = "distribution") -> dict:
    """Pulse-owned analytics + audience + revenue for a published asset."""
    from app.modules.analytics.engine import record_metric
    from app.modules.revenue.engine import record_revenue
    from app.modules.memory.engine import store
    record_metric(db, topic=asset_id, views=views, engagement=engagement,
                  followers_delta=followers_delta)
    if revenue:
        record_revenue(db, "platform", revenue, platform="distribution", actor=actor)
        _emit("REVENUE_RECORDED", {"asset_id": asset_id, "amount": revenue})
    store(db, "outcome", f"asset {asset_id} performance",
          f"views={views} eng={engagement} rev={revenue}", actor=actor)
    audit(db, actor, "distribution.tracked", "asset", asset_id, {"views": views})
    return {"asset_id": asset_id, "views": views, "revenue": revenue}


def _emit(event_type: str, payload: dict) -> None:
    try:
        from app.core.shared import event_bus
        event_bus.publish(event_type, payload, source_pulse="music-pulse")
    except Exception:
        pass
