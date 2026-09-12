"""Factory health & capacity: jobs, timings, provider + asset availability."""
from __future__ import annotations

from sqlalchemy import func

from app.modules.reality_assets import acquisition as assets_mod
from app.modules.renderer import engine as renderer_mod

ACTIVE_STATES = ("planned", "acquiring", "assembling", "rendering")


def report(db) -> dict:
    from app.models.production import ProductionRequest
    active = db.query(func.count()).select_from(ProductionRequest).filter(
        ProductionRequest.state.in_(ACTIVE_STATES)).scalar() or 0
    queued = db.query(func.count()).select_from(ProductionRequest).filter(
        ProductionRequest.state == "created").scalar() or 0
    avg_render = db.query(func.avg(ProductionRequest.render_seconds)).filter(
        ProductionRequest.render_seconds > 0).scalar() or 0.0
    avg_export = db.query(func.avg(ProductionRequest.export_seconds)).filter(
        ProductionRequest.export_seconds > 0).scalar() or 0.0
    exported = db.query(func.count()).select_from(ProductionRequest).filter(
        ProductionRequest.state == "exported").scalar() or 0
    failed = db.query(func.count()).select_from(ProductionRequest).filter(
        ProductionRequest.state == "failed").scalar() or 0
    return {
        "factory": "zoza-factory",
        "active_jobs": int(active),
        "queued_jobs": int(queued),
        "exported_jobs": int(exported),
        "failed_jobs": int(failed),
        "average_render_time": round(float(avg_render), 3),
        "average_export_time": round(float(avg_export), 3),
        "provider_availability": renderer_mod.provider_availability(),
        "asset_availability": assets_mod.catalog_availability(db),
    }
