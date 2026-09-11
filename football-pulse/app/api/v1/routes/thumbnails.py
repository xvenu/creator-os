"""Thumbnail strategy endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.phase4 import ThumbnailStrategy

router = APIRouter(tags=["thumbnails"])


@router.get("/")
async def list_thumbnails(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(ThumbnailStrategy).order_by(ThumbnailStrategy.created_at.desc()).limit(max(limit, 1))
    )).scalars().all()
    return {"count": len(rows), "items": [
        {"thumbnail_id": str(r.id), "thumbnail_text": r.thumbnail_text,
         "emotional_trigger": r.emotional_trigger,
         "click_probability": r.click_probability} for r in rows]}


@router.get("/top")
async def top_thumbnails(limit: int = 10, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(ThumbnailStrategy).order_by(ThumbnailStrategy.click_probability.desc())
        .limit(max(limit, 1))
    )).scalars().all()
    return {"count": len(rows), "items": [
        {"thumbnail_id": str(r.id), "thumbnail_text": r.thumbnail_text,
         "visual_elements": r.visual_elements,
         "click_probability": r.click_probability} for r in rows]}
