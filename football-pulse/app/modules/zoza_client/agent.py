"""Zoza Dispatcher Agent: submit packages, track jobs, collect exports.

Payload shapes:
- {"package": {...}} — build handoff package, submit to factory, track once.
- {"request_id": ...} — poll an existing request, collect export when rendered.
- {"retry_request_id": ...} — re-attempt a failed/queued request.

The agent never renders. Factory unreachable → request stays retryable
(submitted/queued), never failed on first contact.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy import select

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.agents.pipeline import emit_next_task
from app.core.logging import get_logger
from app.db.models.zoza import ZozaExport, ZozaRequest
from app.modules.zoza_client import events
from app.modules.zoza_client.config import MAX_ATTEMPTS
from app.modules.zoza_client.factory import ZozaFactory
from app.modules.zoza_client.package import build_zoza_package, to_zoza_job
from app.modules.zoza_client.store import (
    create_request,
    get_request,
    get_request_by_job,
    record_attempt,
    record_export,
    retries_exhausted,
    transition_request,
    update_factory_status,
)

log = get_logger("agent.zoza_dispatcher")

_session_factory: Callable | None = None


def set_session_factory(factory: Callable | None) -> None:
    global _session_factory
    _session_factory = factory


def _resolve_factory() -> Callable:
    if _session_factory is not None:
        return _session_factory
    from app.core.config import get_settings
    from app.db.session import get_session_factory

    return get_session_factory(get_settings())


class ZozaDispatcherAgent(BaseAgent):
    metadata = AgentMetadata(
        name="zoza_dispatcher",
        description="Submit packages to Zoza factory, track jobs, collect exports",
        version="1.0.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        payload = ctx.payload
        factory = ZozaFactory()
        session_factory = _resolve_factory()
        async with session_factory() as session:
            if "package" in payload:
                result = await self._submit(session, factory, payload["package"])
            elif "request_id" in payload:
                result = await self._monitor(
                    session, factory, uuid.UUID(str(payload["request_id"])))
            elif "retry_request_id" in payload:
                result = await self._retry(
                    session, factory, uuid.UUID(str(payload["retry_request_id"])))
            else:
                raise ValueError("payload needs package, request_id or retry_request_id")
            await session.commit()
            task = await emit_next_task(
                session, "zoza_dispatcher", payload.get("emit_task") or {},
                ref_id=result.get("request_id", ""))
            await session.commit()
        if task is not None:
            result["next_task_id"] = str(task.id)
        return result

    async def _submit(self, session, factory: ZozaFactory, content: dict) -> dict:
        package = build_zoza_package(content)
        job = to_zoza_job(package)
        existing = await get_request_by_job(session, job["job_id"])
        if existing is not None:
            return await self._monitor_by_row(session, factory, existing)
        package_uuid = _as_uuid(content.get("package_id"))
        row = await create_request(session, package_uuid, job["job_id"],
                                   payload=package, priority=package["priority"])
        ping = factory.ping()
        await update_factory_status(session, "zoza-factory", ping["reachable"],
                                    meta={"dir": ping["dir"]})
        if not ping["reachable"]:
            # Retryable: factory down is not a failure.
            events.emit("VIDEO_REQUESTED", {"package_id": package["package_id"],
                                            "state": "queued", "reason": "factory-unreachable"})
            return {"request_id": str(row.id), "zoza_job_id": row.zoza_job_id,
                    "state": row.state, "submitted": False, "reason": "factory-unreachable"}
        await record_attempt(session, row)
        submitted = factory.submit(job)
        if not submitted["ok"]:
            await transition_request(session, row, "failed", error=submitted.get("error"))
            events.emit("VIDEO_REQUESTED", {"package_id": package["package_id"],
                                            "state": "failed", "error": submitted.get("error")})
            return {"request_id": str(row.id), "zoza_job_id": row.zoza_job_id,
                    "state": "failed", "submitted": False}
        await transition_request(session, row, "submitted")
        events.emit("VIDEO_REQUESTED", {"package_id": package["package_id"],
                                        "zoza_job_id": row.zoza_job_id, "state": "submitted"})
        return await self._monitor_by_row(session, factory, row)

    async def _monitor(self, session, factory: ZozaFactory, request_id: uuid.UUID) -> dict:
        row = await get_request(session, request_id)
        if row is None:
            raise ValueError(f"Unknown zoza request: {request_id}")
        return await self._monitor_by_row(session, factory, row)

    async def _monitor_by_row(self, session, factory: ZozaFactory, row: ZozaRequest) -> dict:
        if row.state in ("exported", "failed"):
            return {"request_id": str(row.id), "zoza_job_id": row.zoza_job_id,
                    "state": row.state, "terminal": True}
        poll = factory.poll(row.zoza_job_id)
        if poll["state"] == "submitted":
            return {"request_id": str(row.id), "zoza_job_id": row.zoza_job_id,
                    "state": row.state, "factory": "unseen"}
        if poll["state"] != row.state and poll["state"] in ("queued", "rendering", "rendered"):
            await transition_request(session, row, poll["state"])
            if poll["state"] == "rendering":
                events.emit("VIDEO_RENDER_STARTED",
                            {"zoza_job_id": row.zoza_job_id, "request_id": str(row.id)})
            if poll["state"] == "rendered":
                events.emit("VIDEO_RENDER_FINISHED",
                            {"zoza_job_id": row.zoza_job_id, "request_id": str(row.id)})
        if row.state == "rendered":
            collected = factory.collect_export(row.zoza_job_id)
            if collected["ok"]:
                await record_export(session, row, collected["export"])
                await transition_request(session, row, "exported")
                events.emit("VIDEO_EXPORTED",
                            {"zoza_job_id": row.zoza_job_id, "request_id": str(row.id)})
                return {"request_id": str(row.id), "zoza_job_id": row.zoza_job_id,
                        "state": "exported", "export": collected["export"]}
            return {"request_id": str(row.id), "zoza_job_id": row.zoza_job_id,
                    "state": "rendered", "export_pending": collected.get("error")}
        if poll["state"] == "failed":
            await transition_request(session, row, "failed", error="factory reported FAILED")
            return {"request_id": str(row.id), "zoza_job_id": row.zoza_job_id, "state": "failed"}
        return {"request_id": str(row.id), "zoza_job_id": row.zoza_job_id, "state": row.state}

    async def _retry(self, session, factory: ZozaFactory, request_id: uuid.UUID) -> dict:
        row = await get_request(session, request_id)
        if row is None:
            raise ValueError(f"Unknown zoza request: {request_id}")
        if row.state == "exported":
            return {"request_id": str(row.id), "state": "exported", "terminal": True}
        if await retries_exhausted(row):
            if row.state != "failed":
                await transition_request(session, row, "failed", error="retries exhausted")
            return {"request_id": str(row.id), "state": "failed", "terminal": True,
                    "attempts": row.attempts, "max_attempts": MAX_ATTEMPTS}
        ping = factory.ping()
        if not ping["reachable"]:
            return {"request_id": str(row.id), "state": row.state, "retried": False,
                    "reason": "factory-unreachable"}
        job_file = factory.read_job(row.zoza_job_id)
        if job_file is None:
            # Re-submit the original payload.
            package = dict(row.payload or {})
            job = to_zoza_job({**package, "package_id": package.get(
                "package_id", row.zoza_job_id.replace("fp-", ""))})
            job["job_id"] = row.zoza_job_id
            await record_attempt(session, row)
            submitted = factory.submit(job)
            if not submitted["ok"]:
                return {"request_id": str(row.id), "state": row.state, "retried": False,
                        "error": submitted.get("error")}
            if row.state == "failed":
                await transition_request(session, row, "submitted")
            elif row.state == "created":
                await transition_request(session, row, "submitted")
        else:
            await record_attempt(session, row)
            if row.state == "failed":
                await transition_request(session, row, "submitted")
        return await self._monitor_by_row(session, factory, row)


def _as_uuid(value) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None
