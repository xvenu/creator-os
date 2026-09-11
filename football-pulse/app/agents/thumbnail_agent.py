"""Thumbnail Strategy Agent: click concepts (no image bytes until Phase 5)."""
from __future__ import annotations

import uuid

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.agents.pipeline import emit_next_task, make_resolver
from app.core.logging import get_logger
from app.db.models.phase4 import ThumbnailStrategy
from app.services import thumbnail_service as svc

log = get_logger("agent.thumbnail_strategy")

_session_factory = None
_resolve = make_resolver(globals())


def set_session_factory(factory) -> None:
    globals()["_session_factory"] = factory


class ThumbnailStrategyAgent(BaseAgent):
    metadata = AgentMetadata(
        name="thumbnail_strategy",
        description="Generate thumbnail concepts: text, visuals, emotion, color",
        version="0.4.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        payload = ctx.payload
        jobs: list[dict] = list(payload.get("thumbnails", []))
        if "topic" in payload:
            jobs.append(payload)
        if not jobs:
            return {"generated": 0, "items": []}

        factory = _resolve()
        items: list[dict] = []
        async with factory() as session:
            for job in jobs:
                concept = svc.generate_thumbnail(
                    str(job.get("topic", "football")),
                    str(job.get("content_format", "football_story")),
                    job.get("entities") or {},
                    str(job.get("urgency", "medium")),
                )
                script_id = None
                try:
                    script_id = uuid.UUID(str(job["script_id"])) if job.get("script_id") else None
                except (ValueError, AttributeError):
                    script_id = None
                row = ThumbnailStrategy(
                    script_id=script_id,
                    thumbnail_text=concept["thumbnail_text"],
                    visual_elements=concept["visual_elements"],
                    emotional_trigger=concept["emotional_trigger"],
                    color_strategy=concept["color_strategy"],
                    click_probability=concept["click_probability"],
                    meta={"topic": job.get("topic")},
                )
                session.add(row)
                await session.flush()
                task = await emit_next_task(
                    session, "thumbnail_strategy", payload.get("emit_task") or {},
                    ref_id=str(row.id),
                )
                items.append({**concept, "thumbnail_id": str(row.id),
                              "next_task_id": str(task.id) if task else None})
            await session.commit()

        log.info("thumbnail_strategy_done", generated=len(items))
        return {"generated": len(items), "items": items}
