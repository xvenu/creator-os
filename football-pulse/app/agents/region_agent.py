"""Region Intelligence Agent: monetization-ranked regions per topic."""
from __future__ import annotations

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.agents.pipeline import emit_next_task, make_resolver
from app.core.logging import get_logger
from app.db.models.phase4 import RegionIntelligence
from app.services import memory_service
from app.services import region_service as svc

log = get_logger("agent.region_intelligence")

_session_factory = None
_resolve = make_resolver(globals())


def set_session_factory(factory) -> None:
    globals()["_session_factory"] = factory


class RegionIntelligenceAgent(BaseAgent):
    metadata = AgentMetadata(
        name="region_intelligence",
        description="Rank regions by monetization; recommend language and timing",
        version="0.4.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        payload = ctx.payload
        topics: list[str] = list(payload.get("topics", []))
        if "topic" in payload:
            topics.append(str(payload["topic"]))
        if not topics:
            return {"analyzed": 0, "items": []}

        limit = int(payload.get("limit", 8))
        ranked = svc.rank_regions(limit=limit)
        factory = _resolve()
        items: list[dict] = []
        async with factory() as session:
            for topic in topics:
                for region in ranked:
                    row = RegionIntelligence(
                        region=region["region"],
                        tier=region["tier"],
                        cpm_estimate=region["cpm_estimate"],
                        rpm_estimate=region["rpm_estimate"],
                        football_interest=region["football_interest"],
                        recommended_language=region["recommended_language"],
                        recommended_publish_time=region["recommended_publish_time"],
                        monetization_score=region["monetization_score"],
                        audience_quality=region["audience_quality"],
                        meta={"topic": topic},
                    )
                    session.add(row)
                    await memory_service.observe_region_performance(
                        session, region["region"], region["monetization_score"],
                        region["recommended_publish_time"], topic,
                    )
                    await memory_service.observe_rpm_topic(
                        session, topic, region["rpm_estimate"]
                    )
                await session.flush()
                task = await emit_next_task(
                    session, "region_intelligence", payload.get("emit_task") or {},
                    ref_id=topic,
                )
                items.append({"topic": topic, "regions": ranked,
                              "next_task_id": str(task.id) if task else None})
            await session.commit()

        log.info("region_intelligence_done", analyzed=len(items))
        return {"analyzed": len(items), "items": items}
