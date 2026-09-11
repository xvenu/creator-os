"""Content Planner Agent: opportunities → content calendar."""
from __future__ import annotations

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.agents.pipeline import emit_next_task, make_resolver
from app.core.logging import get_logger
from app.db.models.phase4 import ContentPlan
from app.services import planner_service as svc

log = get_logger("agent.content_planner")

_session_factory = None
_resolve = make_resolver(globals())


def set_session_factory(factory) -> None:
    globals()["_session_factory"] = factory


class ContentPlannerAgent(BaseAgent):
    metadata = AgentMetadata(
        name="content_planner",
        description="Build content calendars: what, when, platforms, priority",
        version="0.4.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        payload = ctx.payload
        opportunities: list[dict] = list(payload.get("opportunities", []))
        if "topic" in payload or "title" in payload:
            opportunities.append(payload)
        if not opportunities:
            return {"planned": 0, "items": []}

        calendar = svc.build_calendar(opportunities)
        factory = _resolve()
        items: list[dict] = []
        async with factory() as session:
            for entry in calendar:
                row = ContentPlan(
                    content_id=entry["content_id"],
                    topic=entry["topic"],
                    publish_priority=entry["publish_priority"],
                    publish_window={**entry["publish_window"],
                                    "next_slot": svc.next_publish_slot(entry["publish_priority"])},
                    platform_targets=entry["platform_targets"],
                    expected_reach=entry["expected_reach"],
                    status="scheduled",
                    meta={"content_type": entry["content_type"]},
                )
                session.add(row)
                await session.flush()
                task = await emit_next_task(
                    session, "content_planner", payload.get("emit_task") or {},
                    ref_id=str(row.id),
                )
                items.append({**entry, "plan_id": str(row.id),
                              "next_task_id": str(task.id) if task else None})
            await session.commit()

        log.info("content_planner_done", planned=len(items))
        return {"planned": len(items), "items": items}
