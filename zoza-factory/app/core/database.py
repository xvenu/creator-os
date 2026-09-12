"""Sync SQLAlchemy engine. SQLite by default (self-contained); Postgres via DATABASE_URL."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

_engine = None
_SessionLocal = None


def _build_engine():
    settings = get_settings()
    url = settings.database_url
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def get_engine():
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


def init_db() -> None:
    from app.models.base import Base
    import app.models.production  # noqa: F401  (register tables)
    Base.metadata.create_all(bind=get_engine())


def reset_engine() -> None:
    """Test hook: drop cached engine/session so settings overrides take effect."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
