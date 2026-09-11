"""Zoza factory endpoints: request / status / exports / retry.

No local rendering exists in this pulse. No provider secrets accepted
or exposed — factory addressing is server-side configuration.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext
from app.api.deps import get_db
from app.db.models.zoza import ZozaExport, ZozaRequest
from app.modules.zoza_client.agent import ZozaDispatcherAgent
from app.modules.zoza_client.factory import ZozaFactory
from app.modules.zoza_client.store import update_factory_status

router = APIRouter(tags=["zoza"])


@router.post("/request")
async def request_video(body: dict, session: AsyncSession = Depends(get_db)) -> dict:
    """Submit a content package to the Zoza factory (never renders locally)."""
    package = body.get("package") or body
    result = await ZozaDispatcherAgent().run(AgentContext(payload={"package": package}))
    if result.status.value != "succeeded":
        raise HTTPException(status_code=422, detail=result.error or "dispatch failed")
    return result.output


@router.get("/status/{request_id}")
async def request_status(request_id: uuid.UUID,
                         session: AsyncSession = Depends(get_db)) -> dict:
    row = await session.get(ZozaRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Zoza request not found")
    return {"request_id": str(row.id), "zoza_job_id": row.zoza_job_id,
            "state": row.state, "attempts": row.attempts,
            "priority": row.priority, "last_error": row.last_error}


@router.get("/exports")
async def list_exports(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(ZozaExport).order_by(ZozaExport.created_at.desc()).limit(max(limit, 1))
    )).scalars().all()
    return {"count": len(rows), "items": [
        {"export_id": str(r.id), "request_id": str(r.request_id) if r.request_id else None,
         "zoza_job_id": r.zoza_job_id, "video_path": r.video_path,
         "thumbnail_path": r.thumbnail_path, "title": r.title,
         "status": r.status} for r in rows]}


@router.post("/retry/{request_id}")
async def retry_request(request_id: uuid.UUID,
                        session: AsyncSession = Depends(get_db)) -> dict:
    result = await ZozaDispatcherAgent().run(
        AgentContext(payload={"retry_request_id": str(request_id)}))
    if result.status.value != "succeeded":
        raise HTTPException(status_code=422, detail=result.error or "retry failed")
    return result.output


@router.get("/factory")
async def factory_health(session: AsyncSession = Depends(get_db)) -> dict:
    ping = ZozaFactory().ping()
    await update_factory_status(session, "zoza-factory", ping["reachable"],
                                meta={"dir": ping["dir"]})
    await session.commit()
    return ping
