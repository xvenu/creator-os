"""Research brief endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.phase4 import ResearchBrief

router = APIRouter(tags=["research"])


@router.get("/")
async def list_briefs(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(ResearchBrief).order_by(ResearchBrief.created_at.desc()).limit(max(limit, 1))
    )).scalars().all()
    return {"count": len(rows), "items": [
        {"brief_id": str(r.id), "topic": r.topic, "confidence": r.confidence,
         "fact_count": len(r.facts or []), "entities": r.entities} for r in rows]}


@router.get("/by-topic")
async def briefs_by_topic(topic: str, session: AsyncSession = Depends(get_db)) -> dict:
    rows = (await session.execute(
        select(ResearchBrief).where(ResearchBrief.topic == topic)
        .order_by(ResearchBrief.created_at.desc()).limit(5)
    )).scalars().all()
    return {"count": len(rows), "items": [
        {"brief_id": str(r.id), "topic": r.topic, "facts": r.facts,
         "timeline": r.timeline, "supporting_points": r.supporting_points,
         "confidence": r.confidence, "references": r.references} for r in rows]}
