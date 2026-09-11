"""SEO asset endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.phase4 import SEOAsset

router = APIRouter(tags=["seo"])


@router.get("/")
async def list_seo(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(SEOAsset).order_by(SEOAsset.created_at.desc()).limit(max(limit, 1))
    )).scalars().all()
    return {"count": len(rows), "items": [
        {"seo_id": str(r.id), "title_options": r.title_options,
         "keywords": r.keywords, "hashtags": r.hashtags, "seo_score": r.seo_score}
        for r in rows]}


@router.get("/top")
async def top_seo(limit: int = 10, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(SEOAsset).order_by(SEOAsset.seo_score.desc()).limit(max(limit, 1))
    )).scalars().all()
    return {"count": len(rows), "items": [
        {"seo_id": str(r.id), "title_options": r.title_options, "seo_score": r.seo_score}
        for r in rows]}
