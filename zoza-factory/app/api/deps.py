"""Request-scoped DB session."""
from __future__ import annotations

from collections.abc import Iterator

from app.core.database import get_session_factory


def get_db() -> Iterator:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
