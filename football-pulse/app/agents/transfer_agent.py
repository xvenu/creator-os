"""Transfer Intelligence Agent: rumors → credibility → probability → upsert → memory."""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.core.logging import get_logger
from app.db.models.phase2 import TransferIntel
from app.services import memory_service, transfer_service as svc

log = get_logger("agent.transfer_intelligence")

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


class TransferIntelligenceAgent(BaseAgent):
    metadata = AgentMetadata(
        name="transfer_intelligence",
        description="Track rumors, score credibility, estimate probabilities",
        version="0.2.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        rumors: list[dict] = list(ctx.payload.get("rumors", []))
        if "player" in ctx.payload:
            rumors.append(ctx.payload)
        if not rumors:
            return {"processed": 0, "items": []}

        factory = _resolve_factory()
        items: list[dict] = []
        async with factory() as session:
            for rumor in rumors:
                intel = svc.process_rumor(rumor)
                # Upsert: merge into open tracking row for same player+destination.
                stmt = (
                    select(TransferIntel)
                    .where(
                        func.lower(TransferIntel.player) == intel["player"].lower(),
                        func.coalesce(func.lower(TransferIntel.to_club), "")
                        == (intel["to_club"] or "").lower(),
                        TransferIntel.status.notin_(["confirmed", "collapsed"]),
                    )
                    .order_by(TransferIntel.updated_at.desc())
                )
                existing = (await session.execute(stmt)).scalars().first()
                if existing is not None and intel["status"] not in ("confirmed",):
                    merged_sources = list(existing.sources or [])
                    for s in intel["sources"]:
                        if s not in merged_sources:
                            merged_sources.append(s)
                    credibility, confidence = svc.score_rumor(merged_sources)
                    existing.from_club = intel["from_club"] or existing.from_club
                    existing.status = intel["status"]
                    existing.credibility_score = credibility
                    existing.confidence = confidence
                    existing.probability = svc.generate_probability(credibility, intel["status"])
                    existing.sources = merged_sources
                    existing.timeline = svc.build_timeline(
                        list(existing.timeline or []), intel["status"], "rumor merged"
                    )
                    existing.last_updated = intel["last_updated"]
                    await session.flush()
                    row = existing
                else:
                    row = TransferIntel(
                        player=intel["player"],
                        from_club=intel["from_club"],
                        to_club=intel["to_club"],
                        status=intel["status"],
                        credibility_score=intel["credibility_score"],
                        confidence=intel["confidence"],
                        probability=intel["probability"],
                        sources=intel["sources"],
                        timeline=svc.build_timeline([], intel["status"], "first report"),
                        last_updated=intel["last_updated"],
                        meta={},
                    )
                    session.add(row)
                    await session.flush()
                await memory_service.observe_transfer(session, row.player, row.to_club)
                items.append(
                    {
                        "player": row.player,
                        "from_club": row.from_club,
                        "to_club": row.to_club,
                        "status": row.status,
                        "credibility_score": row.credibility_score,
                        "confidence": row.confidence,
                        "probability": row.probability,
                        "sources": row.sources,
                        "last_updated": row.last_updated.isoformat() if row.last_updated else None,
                    }
                )
            await session.commit()

        # Highest-probability first.
        items.sort(key=lambda i: i["probability"], reverse=True)
        log.info("transfer_intelligence_done", processed=len(items))
        return {"processed": len(items), "items": items}
