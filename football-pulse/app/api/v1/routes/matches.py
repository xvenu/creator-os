"""Match analysis endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.phase2 import MatchAnalysis

router = APIRouter(tags=["matches"])


def _row_to_dict(row: MatchAnalysis) -> dict:
    return {
        "id": str(row.id),
        "match_id": str(row.match_id) if row.match_id else None,
        "home_club": row.home_club,
        "away_club": row.away_club,
        "league": row.league,
        "status": row.status,
        "key_events": row.key_events,
        "tactical_summary": row.tactical_summary,
        "standout_players": row.standout_players,
        "strengths": row.strengths,
        "weaknesses": row.weaknesses,
        "narrative": row.narrative,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
    }


@router.get("/analysis")
async def list_analyses(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(MatchAnalysis).order_by(MatchAnalysis.created_at.desc()).limit(max(limit, 1))
    rows = (await session.execute(stmt)).scalars().all()
    return {"count": len(rows), "items": [_row_to_dict(r) for r in rows]}


@router.get("/analysis/{analysis_id}")
async def get_analysis(analysis_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> dict:
    row = await session.get(MatchAnalysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return _row_to_dict(row)
