"""Region intelligence endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.phase4 import RegionIntelligence

router = APIRouter(tags=["regions"])


@router.get("/")
async def list_regions(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(RegionIntelligence).order_by(RegionIntelligence.monetization_score.desc())
        .limit(max(limit, 1))
    )).scalars().all()
    return {"count": len(rows), "items": [
        {"region": r.region, "tier": r.tier, "cpm_estimate": r.cpm_estimate,
         "rpm_estimate": r.rpm_estimate, "monetization_score": r.monetization_score,
         "audience_quality": r.audience_quality,
         "recommended_language": r.recommended_language,
         "recommended_publish_time": r.recommended_publish_time} for r in rows]}


@router.get("/top")
async def top_regions(limit: int = 8, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(RegionIntelligence).order_by(RegionIntelligence.monetization_score.desc())
        .limit(max(limit, 1))
    )).scalars().all()
    return {"count": len(rows),
            "items": [{"region": r.region, "monetization_score": r.monetization_score} for r in rows]}


@router.get("/by-tier/{tier}")
async def regions_by_tier(tier: int, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(RegionIntelligence).where(RegionIntelligence.tier == tier)
        .order_by(RegionIntelligence.monetization_score.desc())
    )).scalars().all()
    return {"count": len(rows),
            "items": [{"region": r.region, "monetization_score": r.monetization_score} for r in rows]}
