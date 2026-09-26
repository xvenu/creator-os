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
    _ensure_universal_columns()


def _ensure_universal_columns() -> None:
    """Additive migration for pre-existing sqlite DBs (mirrors 002)."""
    from sqlalchemy import text
    new_cols = {
        "content_type": "VARCHAR(16) DEFAULT 'video'",
        "format_variant": "VARCHAR(32) DEFAULT ''",
        "aspect_ratio": "VARCHAR(16) DEFAULT '16:9'",
        "resolution": "VARCHAR(16) DEFAULT '1080p'",
        "language": "VARCHAR(16) DEFAULT 'en'",
        "narration": "TEXT DEFAULT ''",
        "brand_context": "VARCHAR(256) DEFAULT ''",
        "call_to_action": "VARCHAR(256) DEFAULT ''",
    }
    try:
        with get_engine().begin() as conn:
            existing = {r[1] for r in conn.execute(
                text("PRAGMA table_info(production_requests)")).fetchall()}
            for col, ddl in new_cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE production_requests ADD COLUMN {col} {ddl}"))
    except Exception:
        pass


def reset_engine() -> None:
    """Test hook: drop cached engine/session so settings overrides take effect."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
