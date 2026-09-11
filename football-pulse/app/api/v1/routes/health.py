"""Health endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_settings_dep
from app.core.config import Settings
from app.core.health import check_database, check_redis, overall_status
from app.db.session import get_session_factory
from app.queue.redis_queue import get_redis

router = APIRouter(tags=["health"])


@router.get("/live")
async def liveness() -> dict:
    return {"status": "alive"}


@router.get("/ready")
async def readiness(
    settings: Settings = Depends(get_settings_dep),
    session: AsyncSession = Depends(get_db),
) -> dict:
    await session.close()
    db_status = await check_database(lambda: get_session_factory(settings)())
    try:
        redis_status = await check_redis(get_redis(settings))
    except Exception:
        from app.core.health import DependencyStatus

        redis_status = DependencyStatus.UNKNOWN
    deps = {"database": db_status, "redis": redis_status}
    return {
        "status": overall_status(deps),
        "version": settings.app_version,
        "environment": settings.environment,
        "dependencies": {k: v.value for k, v in deps.items()},
    }
