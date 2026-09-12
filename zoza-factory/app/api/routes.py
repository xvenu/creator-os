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
    return voice_mod.match(body.get("voice_profile", ""), body.get("goal", ""),
                           body.get("style", ""), body.get("target_audience", ""))


@router.post("/timeline/build")
def timeline_build(body: dict):
    narration = body.get("narration", "")
    length = body.get("length_seconds", 0)
    if not narration or not length:
        raise HTTPException(status_code=422, detail="narration and length_seconds required")
    return timeline_mod.build(narration, float(length), body.get("assets", []))


@router.get("/capacity")
def capacity(db=Depends(get_db)):
    return capacity_mod.report(db)
