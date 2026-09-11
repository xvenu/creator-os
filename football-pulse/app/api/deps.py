"""Shared API dependencies."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session_factory


def get_settings_dep() -> Settings:
    return get_settings()


async def get_db() -> AsyncIterator[AsyncSession]:
    settings = get_settings()
    factory = get_session_factory(settings)
    async with factory() as session:
        yield session
