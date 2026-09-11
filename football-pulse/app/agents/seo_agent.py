"""SEO Agent: scripts → titles, descriptions, tags, hashtags."""
from __future__ import annotations

import uuid

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.agents.pipeline import emit_next_task, make_resolver
from app.core.logging import get_logger
from app.db.models.phase4 import SEOAsset
from app.services import memory_service
from app.services import seo_service as svc

log = get_logger("agent.seo")

_session_factory = None
_resolve = make_resolver(globals())


def set_session_factory(factory) -> None:
    globals()["_session_factory"] = factory


class SEOAgent(BaseAgent):
    metadata = AgentMetadata(
        name="seo",
        description="Generate titles, descriptions, keywords and hashtags",
        version="0.4.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        payload = ctx.payload
        jobs: list[dict] = list(payload.get("assets", []))
        if "topic" in payload or "title" in payload:
            jobs.append(payload)
        if not jobs:
            return {"generated": 0, "items": []}

        factory = _resolve()
        items: list[dict] = []
        async with factory() as session:
            for job in jobs:
                topic = str(job.get("topic", job.get("title", "football")))
                seo = svc.generate_seo(topic, str(job.get("summary", "")),
                                       str(job.get("body", "")))
                script_id = None
                try:
                    script_id = uuid.UUID(str(job["script_id"])) if job.get("script_id") else None
                except (ValueError, AttributeError):
                    script_id = None
                row = SEOAsset(
                    script_id=script_id,
                    title_options=seo["title_options"],
                    description=seo["description"],
                    keywords=seo["keywords"],
                    hashtags=seo["hashtags"],
                    seo_score=seo["seo_score"],
                    meta={"topic": topic},
                )
                session.add(row)
                await session.flush()
                if seo["title_options"]:
                    await memory_service.record_observation(
                        session, "best_titles", seo["title_options"][0][:120],
                        extra={"seo_score": seo["seo_score"]},
                    )
                task = await emit_next_task(
                    session, "seo", payload.get("emit_task") or {},
                    ref_id=str(row.id),
                )
                items.append({**seo, "seo_id": str(row.id),
                              "next_task_id": str(task.id) if task else None})
            await session.commit()

        log.info("seo_done", generated=len(items))
        return {"generated": len(items), "items": items}
