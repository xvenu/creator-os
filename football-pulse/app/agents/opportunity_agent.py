"""Content Opportunity Agent: intelligence items → scored, valued opportunities."""
from __future__ import annotations

from collections.abc import Callable

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.core.logging import get_logger
from app.db.models.phase3 import ContentOpportunity
from app.services import executive_service, memory_service, opportunity_service as svc

log = get_logger("agent.content_opportunity")

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


def _tier_from_score(score: float) -> str:
    if score >= 0.80:
        return "immediate"
    if score >= 0.60:
        return "create"
    if score >= 0.40:
        return "monitor"
    return "ignore"


class ContentOpportunityAgent(BaseAgent):
    metadata = AgentMetadata(
        name="content_opportunity",
        description="Convert intelligence into scored, platform-routed content opportunities",
        version="0.3.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        payload = ctx.payload
        raw_items: list[dict] = list(payload.get("items", []))
        if "title" in payload:
            raw_items.append(payload)
        if not raw_items:
            return {"created": 0, "items": []}

        created = svc.rank_opportunities([svc.create_opportunity(i) for i in raw_items])
        factory = _resolve_factory()
        out: list[dict] = []
        async with factory() as session:
            for opp in created:
                rec = executive_service.generate_recommendation({
                    "opportunity_score": opp["score"],
                    "tier": _tier_from_score(opp["score"]),
                    "trend_score": float((opp.get("signals", {}) or {}).get("trend_score", 0.0)),
                    "source_kind": opp["source_kind"],
                    "status": (opp.get("meta", {}) or {}).get("status"),
                })
                platforms = rec["target_platforms"]
                estimates = svc.estimate_value(opp["score"], opp["urgency"], platforms)
                row = ContentOpportunity(
                    title=opp["title"],
                    topic=opp["topic"],
                    source_kind=opp["source_kind"],
                    score=opp["score"],
                    urgency=opp["urgency"],
                    content_type=opp["content_type"],
                    target_platforms=platforms,
                    estimated_reach=estimates["estimated_reach"],
                    estimated_value=estimates["estimated_value"],
                    status="proposed",
                    meta={"signals": opp.get("signals", {})},
                )
                session.add(row)
                await session.flush()
                await memory_service.observe_opportunity_estimates(
                    session, row.topic, row.estimated_reach, 0.0
                )
                out.append(
                    {
                        "opportunity_id": str(row.id),
                        "title": row.title,
                        "topic": row.topic,
                        "score": row.score,
                        "urgency": row.urgency,
                        "content_type": row.content_type,
                        "target_platforms": platforms,
                        "estimated_reach": row.estimated_reach,
                        "estimated_value": row.estimated_value,
                    }
                )
            await session.commit()

        log.info("content_opportunity_done", created=len(out))
        return {"created": len(out), "items": out}
