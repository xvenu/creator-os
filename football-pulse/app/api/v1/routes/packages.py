"""Content package + publishing strategy endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.phase4 import ContentPackage, PublishingStrategy

router = APIRouter(tags=["packages"])


@router.get("/")
async def list_packages(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(ContentPackage).order_by(ContentPackage.created_at.desc()).limit(max(limit, 1))
    )).scalars().all()
    return {"count": len(rows), "items": [
        {"content_package_id": str(r.id), "topic": r.topic,
         "content_type": r.content_type, "status": r.status,
         "target_regions": r.target_regions} for r in rows]}


@router.get("/ready")
async def ready_packages(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(ContentPackage).where(ContentPackage.status == "assembled")
        .order_by(ContentPackage.created_at.desc()).limit(max(limit, 1))
    )).scalars().all()
    return {"count": len(rows), "items": [
        {"content_package_id": str(r.id), "topic": r.topic} for r in rows]}


@router.get("/{package_id}")
async def get_package(package_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> dict:
    row = await session.get(ContentPackage, package_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Package not found")
    strategies = (await session.execute(
        select(PublishingStrategy).where(PublishingStrategy.package_id == row.id)
    )).scalars().all()
    return {
        "content_package_id": str(row.id),
        "topic": row.topic,
        "content_type": row.content_type,
        "status": row.status,
        "quality": row.quality,
        "target_regions": row.target_regions,
        "publishing_strategies": [
            {"best_regions": s.best_regions, "best_language": s.best_language,
             "best_publish_time": s.best_publish_time,
             "platform_schedule": s.platform_schedule,
             "revenue_opportunity_score": s.revenue_opportunity_score}
            for s in strategies
        ],
    }
