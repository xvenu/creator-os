"""Shared pytest fixtures: isolated sqlite DB."""
import os
os.environ["TESTING"] = "1"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def db():
    from app.core.database import Base
    import app.models  # noqa: F401 - register models
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine)
    session = S()
    yield session
    session.close()
