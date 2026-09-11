"""Prediction Agent: match outcomes, scorelines, xG, confidence + accuracy tracking."""
from __future__ import annotations

import uuid
from collections.abc import Callable

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.core.logging import get_logger
from app.db.models import Prediction
from app.services import prediction_service as svc

log = get_logger("agent.prediction")

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


class PredictionAgent(BaseAgent):
    metadata = AgentMetadata(
        name="prediction",
        description="Generate match predictions, probabilities and scorelines",
        version="0.3.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        payload = ctx.payload
        requests: list[dict] = list(payload.get("matches", []))
        if "home_club" in payload:
            requests.append(payload)

        factory = _resolve_factory()
        items: list[dict] = []
        graded: list[dict] = []
        async with factory() as session:
            for req in requests:
                pred = svc.predict_match(req)
                predicted_outcome = svc.predicted_outcome_label(
                    pred["home_win_probability"], pred["draw_probability"], pred["away_win_probability"]
                )
                home = str(req.get("home_club", "Home"))
                away = str(req.get("away_club", "Away"))
                league = req.get("league")
                row = Prediction(
                    match_id=req.get("match_id"),
                    home_win_prob=pred["home_win_probability"],
                    draw_prob=pred["draw_probability"],
                    away_win_prob=pred["away_win_probability"],
                    expected_home_goals=pred["expected_goals"]["home"],
                    expected_away_goals=pred["expected_goals"]["away"],
                    predicted_scoreline=pred["expected_score"],
                    confidence=pred["confidence"],
                    model_version=svc.MODEL_VERSION,
                    meta={
                        "league": league,
                        "label": f"{home} vs {away}",
                        "teams": [home, away],
                        "pattern": f"{(league or 'unknown').lower()}:{predicted_outcome}",
                        "reasoning": pred["reasoning"],
                    },
                )
                session.add(row)
                await session.flush()
                items.append(
                    {
                        "match_id": str(row.match_id) if row.match_id else None,
                        "prediction_id": str(row.id),
                        "home_win_probability": pred["home_win_probability"],
                        "draw_probability": pred["draw_probability"],
                        "away_win_probability": pred["away_win_probability"],
                        "expected_score": pred["expected_score"],
                        "expected_goals": pred["expected_goals"],
                        "confidence": pred["confidence"],
                        "reasoning": pred["reasoning"],
                        "created_at": pred["created_at"].isoformat(),
                    }
                )
            # Grade already-made predictions when results arrive.
            for g in payload.get("results", []):
                try:
                    pred_row = await session.get(Prediction, uuid.UUID(str(g["prediction_id"])))
                except (KeyError, ValueError, AttributeError):
                    continue
                if pred_row is None or pred_row.correct is not None:
                    continue
                result = await svc.record_prediction_result(
                    session, pred_row, int(g["home_score"]), int(g["away_score"])
                )
                graded.append({"prediction_id": str(result.prediction_id), "correct": result.correct})
            await session.commit()

        log.info("prediction_done", predicted=len(items), graded=len(graded))
        return {"predicted": len(items), "graded": len(graded), "items": items, "results": graded}
