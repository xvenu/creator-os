"""Executive endpoints: decisions + summary stats."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models import Task
from app.db.models.phase3 import ContentOpportunity, ExecutiveDecision

router = APIRouter(tags=["executive"])


@router.get("/decisions")
async def list_decisions(limit: int = 20, session: AsyncSession = Depends(get_db)) -> dict:
    stmt = (
        select(ExecutiveDecision)
        .order_by(ExecutiveDecision.opportunity_score.desc())
        .limit(max(limit, 1))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "decision_id": str(r.id),
                "title": r.title,
                "topic": r.topic,
                "priority_level": r.priority_level,
                "opportunity_score": r.opportunity_score,
                "tier": r.tier,
                "recommendation": r.recommendation,
                "reasoning": r.reasoning,
                "urgency": r.urgency,
                "expected_reach": r.expected_reach,
                "expected_engagement": r.expected_engagement,
                "task_ids": r.task_ids,
            }
            for r in rows
        ],
    }


@router.get("/summary")
async def executive_summary(session: AsyncSession = Depends(get_db)) -> dict:
    decisions = (await session.execute(select(ExecutiveDecision))).scalars().all()
    by_tier: dict[str, int] = {}
    for d in decisions:
        by_tier[d.tier] = by_tier.get(d.tier, 0) + 1
    task_count = (await session.execute(select(func.count()).select_from(Task))).scalar() or 0
    opp_count = (await session.execute(select(func.count()).select_from(ContentOpportunity))).scalar() or 0
    tasks_from_decisions = sum(len(d.task_ids or []) for d in decisions)
    return {
        "total_decisions": len(decisions),
        "by_tier": by_tier,
        "total_tasks": task_count,
        "total_opportunities": opp_count,
        "opportunity_conversion_rate": round(tasks_from_decisions / max(opp_count, 1), 3),
        "avg_opportunity_score": round(
            sum(d.opportunity_score for d in decisions) / max(len(decisions), 1), 3
        ),
    }
