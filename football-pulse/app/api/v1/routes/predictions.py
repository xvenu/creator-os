"""Prediction endpoints (Phase 1 `predictions` table + Phase 3 metrics)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models import Prediction
from app.db.models.phase3 import PredictionMetric

router = APIRouter(tags=["predictions"])


def _row_to_dict(row: Prediction) -> dict:
    meta = row.meta or {}
    return {
        "prediction_id": str(row.id),
        "match_id": str(row.match_id) if row.match_id else None,
        "home_win_probability": row.home_win_prob,
        "draw_probability": row.draw_prob,
        "away_win_probability": row.away_win_prob,
        "expected_score": row.predicted_scoreline,
        "expected_goals": {"home": row.expected_home_goals, "away": row.expected_away_goals},
        "confidence": row.confidence,
        "reasoning": meta.get("reasoning", ""),
        "outcome": row.outcome,
        "correct": row.correct,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/")
async def list_predictions(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(Prediction).order_by(Prediction.created_at.desc()).limit(max(limit, 1))
    rows = (await session.execute(stmt)).scalars().all()
    return {"count": len(rows), "items": [_row_to_dict(r) for r in rows]}


@router.get("/top")
async def top_predictions(limit: int = 10, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = (
        select(Prediction)
        .where(Prediction.correct.is_(None))  # pending fixtures only
        .order_by(Prediction.confidence.desc())
        .limit(max(limit, 1))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {"count": len(rows), "items": [_row_to_dict(r) for r in rows]}


@router.get("/metrics")
async def prediction_metrics(session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(select(PredictionMetric))).scalars().all()
    return {
        "scopes": [
            {
                "scope": m.scope,
                "total": m.total,
                "correct": m.correct,
                "exact_scorelines": m.exact_scorelines,
                "accuracy": m.accuracy,
                "avg_confidence": m.avg_confidence,
                "brier_avg": m.brier_avg,
            }
            for m in rows
        ]
    }
