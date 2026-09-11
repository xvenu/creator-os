"""News intelligence endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models import News

router = APIRouter(tags=["news"])


def _row_to_dict(row: News) -> dict:
    return {
        "id": str(row.id),
        "title": row.title,
        "summary": row.body,
        "source": row.source,
        "url": row.source_url,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "importance_score": row.importance_score,
        "breaking_news": row.is_breaking,
        "entities": (row.meta or {}).get("entities", {}),
    }


@router.get("/")
async def list_news(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(News).order_by(News.created_at.desc()).limit(max(limit, 1))
    rows = (await session.execute(stmt)).scalars().all()
    return {"count": len(rows), "items": [_row_to_dict(r) for r in rows]}


@router.get("/top")
async def top_news(limit: int = 10, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = (
        select(News)
        .order_by(News.is_breaking.desc(), News.importance_score.desc())
        .limit(max(limit, 1))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {"count": len(rows), "items": [_row_to_dict(r) for r in rows]}


@router.get("/breaking")
async def breaking_news(limit: int = 10, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = (
        select(News)
        .where(News.is_breaking.is_(True))
        .order_by(News.importance_score.desc())
        .limit(max(limit, 1))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {"count": len(rows), "items": [_row_to_dict(r) for r in rows]}
