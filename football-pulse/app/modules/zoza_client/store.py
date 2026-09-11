"""Zoza request/export/status persistence + retry accounting."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.zoza import FactoryStatus, ZozaExport, ZozaRequest
from app.modules.zoza_client.config import MAX_ATTEMPTS

VALID_REQUEST_TRANSITIONS: dict[str, set[str]] = {
    # Factory state is polled, so jumps (e.g. queued → rendered) are legal.
    "created": {"submitted", "queued", "failed"},
    "submitted": {"queued", "rendering", "rendered", "failed"},
    "queued": {"rendering", "rendered", "failed"},
    "rendering": {"rendered", "failed"},
    "rendered": {"exported", "failed"},
    "exported": set(),
    "failed": {"submitted"},  # retry re-enters the pipeline
}


async def create_request(session: AsyncSession, package_id: uuid.UUID | None,
                         zoza_job_id: str, payload: dict, priority: int = 0) -> ZozaRequest:
    row = ZozaRequest(package_id=package_id, zoza_job_id=zoza_job_id,
                      state="created", attempts=0, priority=priority,
                      payload=payload, meta={})
    session.add(row)
    await session.flush()
    return row


async def get_request(session: AsyncSession, request_id: uuid.UUID) -> ZozaRequest | None:
    return await session.get(ZozaRequest, request_id)


async def get_request_by_job(session: AsyncSession, zoza_job_id: str) -> ZozaRequest | None:
    return (await session.execute(
        select(ZozaRequest).where(ZozaRequest.zoza_job_id == zoza_job_id))).scalar_one_or_none()


async def transition_request(session: AsyncSession, row: ZozaRequest,
                             new_state: str, error: str | None = None) -> ZozaRequest:
    allowed = VALID_REQUEST_TRANSITIONS.get(row.state, set())
    if new_state not in allowed:
        raise ValueError(f"Illegal zoza request transition: {row.state} → {new_state}")
    row.state = new_state
    if error is not None:
        row.last_error = error
    await session.flush()
    return row


async def record_attempt(session: AsyncSession, row: ZozaRequest) -> ZozaRequest:
    row.attempts += 1
    await session.flush()
    return row


async def retries_exhausted(row: ZozaRequest) -> bool:
    return row.attempts >= MAX_ATTEMPTS


async def record_export(session: AsyncSession, request: ZozaRequest, export: dict) -> ZozaExport:
    meta = dict(export.get("metadata") or {})
    row = ZozaExport(
        request_id=request.id, zoza_job_id=export["job_id"],
        video_path=export["video_path"], thumbnail_path=export["thumbnail_path"],
        title=meta.get("title", ""), description=meta.get("description", ""),
        hashtags=meta.get("hashtags", []), status="exported",
        meta={**meta, "package_id": str(request.package_id) if request.package_id else None})
    session.add(row)
    await session.flush()
    return row


async def update_factory_status(session: AsyncSession, component: str,
                                reachable: bool, meta: dict | None = None) -> FactoryStatus:
    row = (await session.execute(
        select(FactoryStatus).where(FactoryStatus.component == component))).scalar_one_or_none()
    if row is None:
        row = FactoryStatus(component=component, reachable=reachable,
                            consecutive_failures=0, meta=meta or {})
        session.add(row)
        await session.flush()
        return row
    row.reachable = reachable
    row.last_checked = dt.datetime.now(dt.timezone.utc)
    row.consecutive_failures = 0 if reachable else row.consecutive_failures + 1
    if meta:
        row.meta = meta
    await session.flush()
    return row
