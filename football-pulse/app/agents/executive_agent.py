"""Executive Agent (CEO): consume intelligence → decisions → tasks → memory."""
from __future__ import annotations

from collections.abc import Callable

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.core.logging import get_logger
from app.db.models import Task
from app.db.models.phase3 import DecisionLog, ExecutiveDecision
from app.services import executive_service as svc
from app.services import memory_service

log = get_logger("agent.executive")

# task_type → owning (future) agent for Phase 4+ consumption.
TASK_ROUTING = {
    "create_script": "script_writer",
    "research_brief": "research",
}

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


class ExecutiveAgent(BaseAgent):
    metadata = AgentMetadata(
        name="executive",
        description="CEO: evaluate opportunities, decide production, generate content tasks",
        version="0.3.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        payload = ctx.payload
        candidates: list[dict] = list(payload.get("decisions", []))
        if "title" in payload or "signals" in payload:
            candidates.append(payload)
        if not candidates:
            return {"decided": 0, "items": [], "tasks_created": 0}

        factory = _resolve_factory()
        items: list[dict] = []
        tasks_created = 0
        async with factory() as session:
            for cand in candidates:
                decision = svc.decide(cand)
                rec = decision["recommendation"]
                row = ExecutiveDecision(
                    title=str(cand.get("title", "Untitled")),
                    topic=str(cand.get("topic", cand.get("title", "Untitled"))),
                    priority_level=decision["priority_level"],
                    opportunity_score=decision["opportunity_score"],
                    recommendation=rec,
                    reasoning=decision["reasoning"],
                    urgency=decision["urgency"],
                    expected_reach=decision["expected_reach"],
                    expected_engagement=decision["expected_engagement"],
                    tier=decision["tier"],
                    meta={"source_kind": cand.get("source_kind", "news"), "signals": cand.get("signals", {})},
                )
                session.add(row)
                await session.flush()
                session.add(DecisionLog(
                    decision_id=row.id,
                    event="decided",
                    detail={"tier": row.tier, "score": row.opportunity_score},
                ))

                task_ids: list[str] = []
                if rec["should_create_content"]:
                    priority = "critical" if decision["tier"] == "immediate" else "high"
                    for task_type in self._plan_tasks(decision["tier"]):
                        task = Task(
                            agent_name=TASK_ROUTING[task_type],
                            kind=task_type,
                            payload={
                                "source": "executive_decision",
                                "decision_id": str(row.id),
                                "topic": row.topic,
                                "title": row.title,
                                "priority": priority,
                                "content_type": rec["content_type"],
                                "target_platforms": rec["target_platforms"],
                            },
                            status="queued",
                        )
                        session.add(task)
                        await session.flush()
                        task_ids.append(str(task.id))
                        session.add(DecisionLog(
                            decision_id=row.id,
                            event="task_generated",
                            detail={"task_id": str(task.id), "task_type": task_type},
                        ))
                        tasks_created += 1
                row.task_ids = task_ids
                await memory_service.observe_executive_decision(
                    session, row.topic, row.tier, row.opportunity_score
                )
                items.append(
                    {
                        "decision_id": str(row.id),
                        "title": row.title,
                        "topic": row.topic,
                        "priority_level": row.priority_level,
                        "opportunity_score": row.opportunity_score,
                        "tier": row.tier,
                        "recommendation": rec,
                        "reasoning": row.reasoning,
                        "urgency": row.urgency,
                        "expected_reach": row.expected_reach,
                        "expected_engagement": row.expected_engagement,
                        "task_ids": task_ids,
                    }
                )
            await session.commit()

        ranked = svc.prioritize_opportunities(items)
        log.info("executive_done", decided=len(items), tasks_created=tasks_created)
        return {"decided": len(items), "tasks_created": tasks_created, "items": ranked}

    @staticmethod
    def _plan_tasks(tier: str) -> list[str]:
        if tier == "immediate":
            return ["create_script", "research_brief"]
        return ["create_script"]
