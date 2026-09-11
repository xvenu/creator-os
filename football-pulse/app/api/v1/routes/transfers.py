"""Transfer intelligence endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.phase2 import TransferIntel

router = APIRouter(tags=["transfers"])


def _row_to_dict(row: TransferIntel) -> dict:
    return {
        "id": str(row.id),
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


@router.get("/")
async def list_transfers(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(TransferIntel).order_by(TransferIntel.probability.desc()).limit(max(limit, 1))
    rows = (await session.execute(stmt)).scalars().all()
    return {"count": len(rows), "items": [_row_to_dict(r) for r in rows]}


@router.get("/top-rumors")
async def top_rumors(limit: int = 10, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = (
        select(TransferIntel)
        .where(TransferIntel.status.notin_(["confirmed", "collapsed"]))
        .order_by(TransferIntel.probability.desc())
        .limit(max(limit, 1))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {"count": len(rows), "items": [_row_to_dict(r) for r in rows]}


@router.get("/confirmed")
async def confirmed_transfers(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = (
        select(TransferIntel)
        .where(TransferIntel.status == "confirmed")
        .order_by(TransferIntel.last_updated.desc())
        .limit(max(limit, 1))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {"count": len(rows), "items": [_row_to_dict(r) for r in rows]}
