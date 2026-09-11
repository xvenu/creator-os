"""Health check system: liveness + readiness (DB + Redis)."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

log = get_logger("core.health")


class DependencyStatus(str, Enum):
    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class HealthReport(BaseModel):
    status: str
    version: str
    environment: str
    dependencies: dict[str, DependencyStatus]


async def check_database(session_factory) -> DependencyStatus:
    try:
        async with session_factory() as session:
            s: AsyncSession = session
            await s.execute(text("SELECT 1"))
        return DependencyStatus.UP
    except Exception as exc:  # noqa: BLE001
        log.warning("health.db_down", error=str(exc))
        return DependencyStatus.DOWN


async def check_redis(redis_client) -> DependencyStatus:
    try:
        if redis_client is None:
            return DependencyStatus.UNKNOWN
        await redis_client.ping()
        return DependencyStatus.UP
    except Exception as exc:  # noqa: BLE001
        log.warning("health.redis_down", error=str(exc))
        return DependencyStatus.DOWN


def overall_status(deps: dict[str, DependencyStatus]) -> str:
    if all(v == DependencyStatus.UP for v in deps.values()):
        return "ok"
    if any(v == DependencyStatus.DOWN for v in deps.values()):
        return "degraded"
    return "ok"
