"""Factory API: requests, planning, execution, assets, rights, voice, timeline, capacity."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.core.config import get_settings
from app.modules.reality_assets import acquisition as assets_mod
from app.modules.rights_validation import validator as rights_mod
from app.modules.timeline_builder import builder as timeline_mod
from app.modules.voice_intelligence import voices as voice_mod
from app.schemas.contract import ProductionRequestIn
from app.services import capacity as capacity_mod
from app.services import pipeline as pipeline_mod

router = APIRouter()


def _db_error(exc: ValueError, code: int = 404) -> HTTPException:
    return HTTPException(status_code=code, detail=str(exc))


@router.post("/requests")
def create_request(body: ProductionRequestIn, db=Depends(get_db)):
    try:
        return pipeline_mod.submit(db, body.model_dump(mode="json"))
    except ValueError as exc:
        raise _db_error(exc, 409)


@router.get("/requests")
def list_requests(db=Depends(get_db)):
    from app.models.production import ProductionRequest
    rows = db.query(ProductionRequest).order_by(ProductionRequest.id.desc()).limit(50).all()
    return [pipeline_mod.serialize(r) for r in rows]


@router.get("/requests/{request_id}")
def get_request(request_id: str, db=Depends(get_db)):
    try:
        return pipeline_mod.serialize(pipeline_mod.get(db, request_id))
    except ValueError as exc:
        raise _db_error(exc)


@router.post("/requests/{request_id}/plan")
def plan_request(request_id: str, db=Depends(get_db)):
    try:
        return pipeline_mod.plan(db, request_id,
                                 min_trust=get_settings().reality_min_trust)
    except ValueError as exc:
        raise _db_error(exc)


@router.post("/requests/{request_id}/execute")
def execute_request(request_id: str, db=Depends(get_db)):
    try:
        return pipeline_mod.execute(db, request_id, get_settings().output_dir,
                                    min_trust=get_settings().reality_min_trust)
    except ValueError as exc:
        raise _db_error(exc)


@router.get("/exports/{request_id}")
def get_export(request_id: str, db=Depends(get_db)):
    try:
        row = pipeline_mod.get(db, request_id)
    except ValueError as exc:
        raise _db_error(exc)
    if row.state != "exported":
        raise HTTPException(status_code=409,
                            detail=f"request not exported (state={row.state})")
    return row.export_json


@router.get("/assets/catalog")
def assets_catalog(db=Depends(get_db)):
    from app.models.production import ProductionAsset
    assets_mod.seed_catalog(db)
    rows = db.query(ProductionAsset).all()
    return [{"asset_id": r.asset_id, "kind": r.kind, "category": r.category,
             "source": r.source, "license": r.license,
             "trust_score": r.trust_score, "rights_status": r.rights_status,
             "duration_seconds": r.duration_seconds} for r in rows]


@router.post("/assets/acquire")
def assets_acquire(body: dict, db=Depends(get_db)):
    sources = body.get("sources", [])
    evidence = body.get("evidence", [])
    min_trust = float(body.get("min_trust", get_settings().reality_min_trust))
    candidates = [assets_mod.normalize_source(s) for s in sources]
    candidates += [assets_mod.normalize_evidence(e) for e in evidence]
    mode = body.get("production_mode", "REALITY_FIRST")
    report = rights_mod.validate_batch(candidates, production_mode=mode)
    usable = [a for a in report["usable"]
              if float(a.get("trust_score", 0.0)) >= min_trust or a.get("evidence_backed")]
    return {"candidates": len(candidates), "usable": assets_mod.order(usable),
            "blocked": report["blocked"], "summary": report["summary"]}


@router.post("/rights/validate")
def rights_validate(body: dict):
    if "assets" in body:
        return rights_mod.validate_batch(
            body["assets"], production_mode=body.get("production_mode", "REALITY_FIRST"))
    result = rights_mod.validate(body.get("rights_status", ""), body.get("license", ""))
    return {**result, "usable_in_mode": {
        m: rights_mod.is_usable(result, m)
        for m in ("REALITY_ONLY", "REALITY_FIRST", "HYBRID", "AI_CREATIVE")}}


@router.post("/voice/match")
def voice_match(body: dict):
    explicit = (body.get("voice_profile", "") or "").strip()
    if explicit:
        return voice_mod.match(explicit, body.get("goal", ""),
                               body.get("style", ""), body.get("target_audience", ""))
    # No explicit profile: keyword/audience signals first, content default only as fallback.
    result = voice_mod.match("", body.get("goal", ""),
                             body.get("style", ""), body.get("target_audience", ""))
    if result.get("reason", "").startswith("no signal matched"):
        from app.modules import content_types as ct_mod
        default = ct_mod.default_voice_for(body.get("content_type", "video"))
        if result.get("profile") != default:
            return voice_mod.match(default, body.get("goal", ""),
                                   body.get("style", ""), body.get("target_audience", ""))
    return result


@router.post("/timeline/build")
def timeline_build(body: dict):
    narration = body.get("narration", "")
    length = body.get("length_seconds", 0)
    if not narration or not length:
        raise HTTPException(status_code=422, detail="narration and length_seconds required")
    return timeline_mod.build_for_content(
        narration, float(length), body.get("assets", []),
        content_type=body.get("content_type", "video"),
        call_to_action=body.get("call_to_action", ""))


@router.get("/capacity")
def capacity(db=Depends(get_db)):
    return capacity_mod.report(db)


@router.get("/capabilities")
def capabilities():
    """Discovery for ANY pulse: families, modes, voices, limits."""
    from app.modules import content_types as ct_mod
    from app.modules import ai_generation as ai_mod
    from app.modules.renderer import engine as renderer_mod
    from app.modules.voice_intelligence import voices as voice_mod
    from app.schemas.contract import KNOWN_PULSES, ProductionMode
    return {
        "factory": "zoza-factory",
        "pulse_contract": "Contract V2 — any pulse may request (no allow-list)",
        "known_pulses": list(KNOWN_PULSES),
        "content_types": ct_mod.describe(),
        "production_modes": [m.value for m in ProductionMode],
        "voices": sorted(voice_mod.PROFILES),
        "render_providers": renderer_mod.provider_availability()["render"],
        "ai_providers": ai_mod.provider_availability(),
        "max_length_seconds": 10800,
        "guarantees": [
            "Pulse decides WHAT, Zoza decides HOW",
            "AI is always the last option",
            "BLOCKED rights never usable",
            "video length == narration length",
            "exports are rendered, never published",
        ],
    }


@router.get("/content-types")
def content_types():
    from app.modules import content_types as ct_mod
    return {"content_types": ct_mod.describe()}


@router.post("/pulses/register")
def pulse_register(body: dict):
    """Register ANY pulse (present or future). No allow-list: the name is
    recorded in the event bus and echoed with current capabilities."""
    from app.services import creator_os as cos
    name = str(body.get("pulse", "") or body.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=422, detail="pulse name required")
    if len(name) > 64:
        raise HTTPException(status_code=422, detail="pulse name too long")
    cos.emit("PULSE_REGISTERED", {"pulse": name,
                                 "content_types": body.get("content_types", []),
                                 "notes": body.get("notes", "")})
    cos.heartbeat()
    from app.modules import content_types as ct_mod
    return {"pulse": name, "registered": True,
            "factory": "zoza-factory",
            "content_types": ct_mod.families(),
            "note": "no allow-list enforced — this pulse may now submit Contract V2 requests"}
