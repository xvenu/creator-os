"""Research Agent: intelligence items → enriched research briefs."""
from __future__ import annotations

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.agents.pipeline import emit_next_task, make_resolver
from app.core.logging import get_logger
from app.db.models.phase4 import ResearchBrief
from app.services import research_service as svc

log = get_logger("agent.research")

_session_factory = None
_resolve = make_resolver(globals())


def set_session_factory(factory) -> None:
    globals()["_session_factory"] = factory


class ResearchAgent(BaseAgent):
    metadata = AgentMetadata(
        name="research",
        description="Aggregate intelligence into enriched research briefs",
        version="0.4.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        payload = ctx.payload
        jobs: list[dict] = list(payload.get("briefs", []))
        if "topic" in payload:
            jobs.append(payload)
        if not jobs:
            return {"researched": 0, "items": []}

        factory = _resolve()
        items: list[dict] = []
        async with factory() as session:
            for job in jobs:
                topic = str(job.get("topic", "untitled"))
                intel = list(job.get("items", []))
                brief = svc.build_brief(topic, intel)
                row = ResearchBrief(
                    topic=topic,
                    facts=brief["facts"],
                    entities=brief["entities"],
                    timeline=brief["timeline"],
                    supporting_points=brief["supporting_points"],
                    confidence=brief["confidence"],
                    references=brief["references"],
                    meta={"expanded_topics": brief["expanded_topics"]},
                )
                session.add(row)
                await session.flush()
                task = await emit_next_task(
                    session, "research", payload.get("emit_task") or {},
                    ref_id=str(row.id),
                )
                items.append({**brief, "brief_id": str(row.id),
                              "next_task_id": str(task.id) if task else None})
            await session.commit()

        log.info("research_done", researched=len(items))
        return {"researched": len(items), "items": items}
