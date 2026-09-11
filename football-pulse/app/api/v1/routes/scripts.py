"""Script endpoints (Phase 1 `scripts` table)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models import Script

router = APIRouter(tags=["scripts"])


def _row(r: Script) -> dict:
    return {"script_id": str(r.id), "title": r.title, "kind": r.kind,
            "status": r.status,
            "quality": (r.retention_notes or {}).get("quality", {}),
            "content_format": (r.meta or {}).get("content_format")}


@router.get("/")
async def list_scripts(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(Script).order_by(Script.created_at.desc()).limit(max(limit, 1))
    )).scalars().all()
    return {"count": len(rows), "items": [_row(r) for r in rows]}


@router.get("/approved")
async def approved_scripts(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(Script).where(Script.status == "approved")
        .order_by(Script.created_at.desc()).limit(max(limit, 1))
    )).scalars().all()
    return {"count": len(rows), "items": [_row(r) for r in rows]}
