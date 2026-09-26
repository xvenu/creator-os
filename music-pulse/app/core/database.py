"""SQLAlchemy database setup."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine():
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)


engine = _engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_publish_idempotency_columns()


def _ensure_publish_idempotency_columns() -> None:
    """Additive migration for pre-existing sqlite DBs (mirrors 008)."""
    from sqlalchemy import text
    cols = {
        "idempotency_key": "VARCHAR(64) DEFAULT ''",
        "target_account": "VARCHAR(128) DEFAULT ''",
        "content_version": "VARCHAR(32) DEFAULT 'v1'",
        "remote_id": "VARCHAR(256) DEFAULT ''",
        "remote_status": "VARCHAR(32) DEFAULT ''",
        "published_at": "TIMESTAMP",
    }
    try:
        with engine.begin() as conn:
            existing = {r[1] for r in conn.execute(
                text("PRAGMA table_info(publish_jobs)")).fetchall()}
            for col, ddl in cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE publish_jobs ADD COLUMN {col} {ddl}"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_publish_jobs_idemkey "
                              "ON publish_jobs (idempotency_key)"))
    except Exception:
        pass
