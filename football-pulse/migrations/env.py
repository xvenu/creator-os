"""Alembic environment (sync engine for migrations)."""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.db.base import Base
import app.db.models  # noqa: F401 — register models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
SYNC_URL = settings.sync_database_url.replace("postgresql://", "postgresql+psycopg2://")

engine = create_engine(SYNC_URL, pool_pre_ping=True)


def run_migrations_offline() -> None:
    context.configure(url=SYNC_URL, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
