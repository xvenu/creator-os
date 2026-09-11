"""Content opportunity endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.phase3 import ContentOpportunity

router = APIRouter(tags=["opportunities"])


def _row_to_dict(row: ContentOpportunity) -> dict:
    return {
        "opportunity_id": str(row.id),
        "title": row.title,
        "topic": row.topic,
        "score": row.score,
        "urgency": row.urgency,
        "content_type": row.content_type,
        "target_platforms": row.target_platforms,
        "estimated_reach": row.estimated_reach,
        "estimated_value": row.estimated_value,
        "status": row.status,
    }


@router.get("/")
async def list_opportunities(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(ContentOpportunity).order_by(ContentOpportunity.score.desc()).limit(max(limit, 1))
    rows = (await session.execute(stmt)).scalars().all()
    return {"count": len(rows), "items": [_row_to_dict(r) for r in rows]}


@router.get("/top")
async def top_opportunities(limit: int = 10, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(ContentOpportunity).order_by(ContentOpportunity.score.desc()).limit(max(limit, 1))
    rows = (await session.execute(stmt)).scalars().all()
    return {"count": len(rows), "items": [_row_to_dict(r) for r in rows]}


@router.get("/high-priority")
async def high_priority(limit: int = 10, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = (
        select(ContentOpportunity)
        .where(ContentOpportunity.urgency.in_(["critical", "high"]))
        .order_by(ContentOpportunity.score.desc())
        .limit(max(limit, 1))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {"count": len(rows), "items": [_row_to_dict(r) for r in rows]}
