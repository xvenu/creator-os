"""Campaign intelligence endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.phase2 import Campaign, CampaignOpportunity

router = APIRouter(tags=["campaigns"])


@router.get("/")
async def list_campaigns(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(Campaign).order_by(Campaign.created_at.desc()).limit(max(limit, 1))
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": str(r.id),
                "campaign_name": r.campaign_name,
                "platform": r.platform,
                "payout_model": r.payout_model,
                "payout_estimate": r.payout_estimate,
                "requirements": r.requirements,
                "niche": r.niche,
                "active": r.active,
                "score": None,
            }
            for r in rows
        ],
    }


@router.get("/top")
async def top_opportunities(limit: int = 10, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = (
        select(CampaignOpportunity)
        .order_by(CampaignOpportunity.score.desc())
        .limit(max(limit, 1))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "campaign_name": r.campaign_name,
                "platform": r.platform,
                "payout_estimate": r.payout_estimate,
                "score": r.score,
                "roi_estimate": r.roi_estimate,
                "risk_score": r.risk_score,
                "recommended": r.recommended,
            }
            for r in rows
        ],
    }


@router.get("/active")
async def active_campaigns(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = (
        select(Campaign)
        .where(Campaign.active.is_(True))
        .order_by(Campaign.payout_estimate.desc())
        .limit(max(limit, 1))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": str(r.id),
                "campaign_name": r.campaign_name,
                "platform": r.platform,
                "payout_model": r.payout_model,
                "payout_estimate": r.payout_estimate,
                "niche": r.niche,
                "active": r.active,
            }
            for r in rows
        ],
    }
