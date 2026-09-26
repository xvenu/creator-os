"""Production pipeline state machine.

created → planned → acquiring → assembling → rendering → exported | failed.

Each transition persists the request row. Render/export stages are timed
for the capacity report. Events go to the shared bus (fail-open).
"""
from __future__ import annotations

import time

from app.modules.reality_assets import acquisition as assets_mod
from app.modules.reality_production_director import director as director_mod
from app.modules.renderer import engine as renderer_mod
from app.services import creator_os as cos


def _touch(row, state: str) -> None:
    row.state = state
    row.updated_at = time.time()


def submit(db, data: dict) -> dict:
    """Persist a new Contract V2 request in state=created."""
    from app.models.production import ProductionRequest
    if db.query(ProductionRequest).filter_by(request_id=data["request_id"]).first():
        raise ValueError(f"request {data['request_id']} already exists")
    from app.modules import content_types as ct_mod
    row = ProductionRequest(
        request_id=data["request_id"], pulse=data.get("pulse", ""),
        goal=data["goal"], style=data.get("style", ""),
        length_seconds=int(data["length_seconds"]),
        urgency=str(data.get("urgency", "normal")),
        production_mode=str(data.get("production_mode", "REALITY_FIRST")),
        ai_generation_allowed=bool(data.get("ai_generation_allowed", False)),
        sources=list(data.get("sources", [])), evidence=list(data.get("evidence", [])),
        voice_profile=data.get("voice_profile", ""),
        target_audience=data.get("target_audience", ""),
        priority=int(data.get("priority", 0)), state="created",
        content_type=ct_mod.normalize(data.get("content_type", "video")),
        format_variant=str(data.get("format_variant", "")),
        aspect_ratio=str(data.get("aspect_ratio", "16:9") or "16:9"),
        resolution=str(data.get("resolution", "1080p") or "1080p"),
        language=str(data.get("language", "en") or "en"),
        narration=str(data.get("narration", "") or ""),
        brand_context=str(data.get("brand_context", "") or ""),
        call_to_action=str(data.get("call_to_action", "") or ""))
    db.add(row)
    db.commit()
    db.refresh(row)
    assets_mod.seed_catalog(db)
    cos.emit("VIDEO_REQUESTED", {"request_id": row.request_id, "pulse": row.pulse,
                                "content_type": row.content_type})
    return serialize(row)


def get(db, request_id: str):
    from app.models.production import ProductionRequest
    row = db.query(ProductionRequest).filter_by(request_id=request_id).first()
    if row is None:
        raise ValueError(f"request {request_id} not found")
    return row


def plan(db, request_id: str, min_trust: float = 0.6) -> dict:
    """created → planned: director decision + persisted strategy."""
    from app.models.production import ProductionAsset
    row = get(db, request_id)
    catalog = [{"source": r.source, "license": r.license, "trust_score": r.trust_score,
                "rights_status": r.rights_status, "kind": r.kind, "category": r.category,
                "duration_seconds": r.duration_seconds,
                "tags": (r.meta_json or {}).get("tags", [])}
               for r in db.query(ProductionAsset).all()]
    req = serialize(row)
    req["_catalog_assets"] = catalog
    decision = director_mod.decide(req, min_trust=min_trust)
    row.strategy_json = decision["strategy"]
    row.timeline_json = decision["timeline"]
    _touch(row, "planned")
    db.commit()
    return decision


def execute(db, request_id: str, output_dir: str, min_trust: float = 0.6) -> dict:
    """Run the full pipeline synchronously. Returns the export manifest."""
    from app.core.config import get_settings
    output_dir = output_dir or get_settings().output_dir
    row = get(db, request_id)
    try:
        if row.state == "created":
            plan(db, request_id, min_trust=min_trust)
            row = get(db, request_id)
        _touch(row, "acquiring")
        db.commit()
        strategy = row.strategy_json or {}
        timeline = row.timeline_json or {}
        voice_profile = (strategy.get("voice_strategy") or row.voice_profile or "documentary")

        from app.modules.voice_intelligence import voices as voice_mod
        voice = voice_mod.match(voice_profile, row.goal, row.style, row.target_audience)

        _touch(row, "assembling")
        db.commit()
        renderer_mod.assemble(request_id, timeline, voice, output_dir)

        _touch(row, "rendering")
        db.commit()
        ct = getattr(row, "content_type", "video") or "video"
        cos.emit("VIDEO_RENDER_STARTED", {"request_id": request_id, "content_type": ct})
        rendered = renderer_mod.render_video(request_id, timeline, output_dir)
        row.render_seconds = rendered["render_seconds"]
        cos.emit("VIDEO_RENDER_FINISHED", {"request_id": request_id, "content_type": ct})

        metadata = {"title": row.goal, "pulse": row.pulse,
                    "content_type": getattr(row, "content_type", "video") or "video",
                    "format_variant": getattr(row, "format_variant", "") or "",
                    "aspect_ratio": getattr(row, "aspect_ratio", "16:9") or "16:9",
                    "resolution": getattr(row, "resolution", "1080p") or "1080p",
                    "language": getattr(row, "language", "en") or "en",
                    "production_mode": row.production_mode,
                    "strategy": strategy.get("strategy", ""),
                    "structure": (timeline.get("structure", "beats")),
                    "render_profile": timeline.get("render_profile", ""),
                    "reality_ratio": strategy.get("reality_ratio", 1.0),
                    "voice_profile": voice.get("profile", "")}
        result = renderer_mod.export_package(
            request_id, rendered["video_path"], rendered["thumbnail_path"],
            metadata, output_dir)
        row.export_seconds = result["export_seconds"]
        row.export_json = result["export"]
        _touch(row, "exported")
        db.commit()
        cos.heartbeat()
        cos.emit("VIDEO_EXPORTED", {"request_id": request_id, "job_id": request_id,
                                   "content_type": ct})
        cos.validate_export_against_shared(result["export"])
        return result["export"]
    except Exception as exc:
        row.state = "failed"
        row.error = str(exc)[:500]
        row.updated_at = time.time()
        db.commit()
        cos.notify_failure(f"zoza-factory: request {request_id} failed: {exc}")
        raise


def serialize(row) -> dict:
    return {
        "request_id": row.request_id, "pulse": row.pulse, "goal": row.goal,
        "style": row.style, "length_seconds": row.length_seconds,
        "urgency": row.urgency, "production_mode": row.production_mode,
        "ai_generation_allowed": row.ai_generation_allowed,
        "sources": row.sources, "evidence": row.evidence,
        "voice_profile": row.voice_profile, "target_audience": row.target_audience,
        "priority": row.priority, "state": row.state,
        "content_type": getattr(row, "content_type", "video") or "video",
        "format_variant": getattr(row, "format_variant", "") or "",
        "aspect_ratio": getattr(row, "aspect_ratio", "16:9") or "16:9",
        "resolution": getattr(row, "resolution", "1080p") or "1080p",
        "language": getattr(row, "language", "en") or "en",
        "narration": getattr(row, "narration", "") or "",
        "brand_context": getattr(row, "brand_context", "") or "",
        "call_to_action": getattr(row, "call_to_action", "") or "",
        "strategy": row.strategy_json, "timeline": row.timeline_json,
        "export": row.export_json, "error": row.error,
        "render_seconds": row.render_seconds, "export_seconds": row.export_seconds,
    }
