"""Match Analysis Agent: form → momentum → tactics → narrative → persist."""
from __future__ import annotations

from collections.abc import Callable

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.core.logging import get_logger
from app.db.models.phase2 import MatchAnalysis
from app.services import match_analysis_service as svc

log = get_logger("agent.match_analysis")

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


class MatchAnalysisAgent(BaseAgent):
    metadata = AgentMetadata(
        name="match_analysis",
        description="Analyze matches, tactics, talking points and trends",
        version="0.2.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        payload = ctx.payload
        requests: list[dict] = list(payload.get("analyses", []))
        if "home_club" in payload:
            requests.append(payload)
        if not requests:
            return {"analyzed": 0, "items": []}

        factory = _resolve_factory()
        items: list[dict] = []
        async with factory() as session:
            for req in requests:
                analysis = svc.analyze_match(req)
                row = MatchAnalysis(
                    match_id=analysis.get("match_id"),
                    home_club=str(req.get("home_club", "")),
                    away_club=str(req.get("away_club", "")),
                    league=req.get("league"),
                    status=str(req.get("status", "upcoming")),
                    key_events=analysis["key_events"],
                    tactical_summary=analysis["tactical_summary"],
                    standout_players=analysis["standout_players"],
                    strengths=analysis["strengths"],
                    weaknesses=analysis["weaknesses"],
                    momentum=analysis["momentum"],
                    form=analysis["form"],
                    narrative=analysis["narrative"],
                    meta={},
                )
                session.add(row)
                await session.flush()
                items.append(
                    {
                        "match_id": str(row.match_id) if row.match_id else None,
                        "analysis_id": str(row.id),
                        "key_events": analysis["key_events"],
                        "tactical_summary": analysis["tactical_summary"],
                        "standout_players": analysis["standout_players"],
                        "strengths": analysis["strengths"],
                        "weaknesses": analysis["weaknesses"],
                        "narrative": analysis["narrative"],
                        "generated_at": analysis["generated_at"].isoformat(),
                    }
                )
            await session.commit()

        log.info("match_analysis_done", analyzed=len(items))
        return {"analyzed": len(items), "items": items}
