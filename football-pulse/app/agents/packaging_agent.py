"""Packaging Agent: script + SEO + thumbnail + regions → content package."""
from __future__ import annotations

import uuid

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.agents.pipeline import emit_next_task, make_resolver
from app.core.logging import get_logger
from app.db.models.phase4 import ContentPackage, PublishingStrategy
from app.services import packaging_service as svc

log = get_logger("agent.packaging")

_session_factory = None
_resolve = make_resolver(globals())


def set_session_factory(factory) -> None:
    globals()["_session_factory"] = factory


class PackagingAgent(BaseAgent):
    metadata = AgentMetadata(
        name="packaging",
        description="Assemble publish-ready content packages + rollout strategies",
        version="0.4.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        payload = ctx.payload
        jobs: list[dict] = list(payload.get("packages", []))
        if "script" in payload:
            jobs.append(payload)
        if not jobs:
            return {"packaged": 0, "items": []}

        factory = _resolve()
        items: list[dict] = []
        async with factory() as session:
            for job in jobs:
                package = svc.assemble_package(job)
                strategy = svc.build_publishing_strategy(
                    {"platform_targets": job.get("platform_targets", ["youtube", "tiktok"])},
                    package["opportunity_score"],
                    job.get("regions"),
                )
                row = ContentPackage(
                    topic=package["topic"],
                    content_type=package["content_type"],
                    brief_id=_as_uuid(job.get("brief_id")),
                    plan_id=_as_uuid(job.get("plan_id")),
                    script_id=_as_uuid(job.get("script", {}).get("script_id") or job.get("script_id")),
                    seo_id=_as_uuid(job.get("seo", {}).get("seo_id") or job.get("seo_id")),
                    thumbnail_id=_as_uuid(job.get("thumbnail", {}).get("thumbnail_id") or job.get("thumbnail_id")),
                    target_regions=package["target_regions"],
                    quality=package["quality"],
                    status=package["status"],
                    meta={"opportunity_score": package["opportunity_score"]},
                )
                session.add(row)
                await session.flush()
                strat_row = PublishingStrategy(
                    package_id=row.id,
                    best_regions=strategy["best_regions"],
                    best_language=strategy["best_language"],
                    best_publish_time=strategy["best_publish_time"],
                    platform_schedule=strategy["platform_schedule"],
                    revenue_opportunity_score=strategy["revenue_opportunity_score"],
                    meta={},
                )
                session.add(strat_row)
                await session.flush()
                task = await emit_next_task(
                    session, "packaging", payload.get("emit_task") or {},
                    ref_id=str(row.id),
                )
                items.append({
                    "content_package_id": str(row.id),
                    "script": package["script"],
                    "seo": package["seo"],
                    "thumbnail_strategy": package["thumbnail_strategy"],
                    "target_regions": package["target_regions"],
                    "publishing_strategy": {**strategy, "strategy_id": str(strat_row.id)},
                    "status": package["status"],
                    "next_task_id": str(task.id) if task else None,
                })
            await session.commit()

        log.info("packaging_done", packaged=len(items))
        return {"packaged": len(items), "items": items}


def _as_uuid(value) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None
