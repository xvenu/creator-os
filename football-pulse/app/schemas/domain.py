"""Pydantic v2 schemas for API I/O."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class NewsIn(BaseModel):
    source: str
    source_url: str
    title: str
    body: str | None = None
    content_hash: str
    importance_score: float = 0.0
    is_breaking: bool = False
    published_at: dt.datetime | None = None
    meta: dict = Field(default_factory=dict)


class NewsOut(NewsIn):
    id: uuid.UUID
    created_at: dt.datetime
    updated_at: dt.datetime


class TaskIn(BaseModel):
    agent_name: str
    kind: str = "run"
    payload: dict = Field(default_factory=dict)
    max_attempts: int = 3


class TaskOut(BaseModel):
    id: uuid.UUID
    agent_name: str
    kind: str
    status: str
    attempts: int
    payload: dict
    result: dict | None = None
    error: str | None = None
    created_at: dt.datetime
    updated_at: dt.datetime


class PredictionIn(BaseModel):
    match_id: uuid.UUID | None = None
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    expected_home_goals: float = 1.4
    expected_away_goals: float = 1.2
    predicted_scoreline: str | None = None
    confidence: float = 0.5


class MemoryIn(BaseModel):
    kind: str
    key: str
    value: dict = Field(default_factory=dict)
    confidence: float = 0.5


class MemoryOut(MemoryIn):
    id: uuid.UUID
    created_at: dt.datetime
    updated_at: dt.datetime
