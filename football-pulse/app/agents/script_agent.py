"""Script Writer Agent: briefs → quality-gated scripts (Phase 1 `scripts` table)."""
from __future__ import annotations

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.agents.pipeline import emit_next_task, make_resolver
from app.core.logging import get_logger
from app.db.models import Script
from app.services import memory_service
from app.services import script_service as svc

log = get_logger("agent.script_writer")

_session_factory = None
_resolve = make_resolver(globals())


def set_session_factory(factory) -> None:
    globals()["_session_factory"] = factory


class ScriptWriterAgent(BaseAgent):
    metadata = AgentMetadata(
        name="script_writer",
        description="Write retention-optimized scripts with quality gating",
        version="0.4.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        payload = ctx.payload
        jobs: list[dict] = list(payload.get("scripts", []))
        if "brief" in payload or "topic" in payload:
            jobs.append(payload)
        if not jobs:
            return {"written": 0, "approved": 0, "rejected": 0, "items": []}

        factory = _resolve()
        items: list[dict] = []
        approved = rejected = 0
        async with factory() as session:
            for job in jobs:
                brief = job.get("brief") or {"topic": job.get("topic", "football"),
                                             "facts": job.get("facts", []),
                                             "supporting_points": job.get("supporting_points", []),
                                             "entities": job.get("entities", {})}
                content_format = str(job.get("content_format", "football_story"))
                length = str(job.get("length", "60s"))
                script = svc.generate_script(brief, content_format, length)
                quality = svc.score_quality(script, brief)
                status = "approved" if quality["approved"] else "rejected"
                if quality["approved"]:
                    approved += 1
                else:
                    rejected += 1
                row = Script(
                    title=script["title"],
                    kind="short" if length in ("30s", "60s") else "long_form",
                    body=f"{script['hook']}\n\n{script['body']}\n\n{script['outro']}",
                    status=status,
                    fact_check_status="pending",
                    retention_notes={"quality": quality,
                                     "estimated_duration": script["estimated_duration"]},
                    meta={"content_format": content_format, "length": length,
                          "brief_topic": brief.get("topic")},
                )
                session.add(row)
                await session.flush()
                await memory_service.observe_script_quality(
                    session, script["title"], script["hook"],
                    content_format, quality["overall_score"], quality["approved"],
                )
                task = await emit_next_task(
                    session, "script_writer", payload.get("emit_task") or {},
                    ref_id=str(row.id),
                )
                items.append({
                    "script_id": str(row.id),
                    "title": script["title"],
                    "hook": script["hook"],
                    "body": script["body"],
                    "outro": script["outro"],
                    "estimated_duration": script["estimated_duration"],
                    "quality": quality,
                    "status": status,
                    "next_task_id": str(task.id) if task else None,
                })
            await session.commit()

        log.info("script_writer_done", written=len(items), approved=approved, rejected=rejected)
        return {"written": len(items), "approved": approved, "rejected": rejected, "items": items}
