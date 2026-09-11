"""Phase 3 Pydantic schemas — prediction, opportunity and executive I/O."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


# --- Prediction ---
class PredictionMatchRequest(BaseModel):
    match_id: uuid.UUID | None = None
    home_club: str
    away_club: str
    league: str | None = None
    home_form: dict = Field(default_factory=dict)
    away_form: dict = Field(default_factory=dict)
    h2h: list[str] = Field(default_factory=list)


class PredictionOut(BaseModel):
    prediction_id: uuid.UUID | None = None
    match_id: uuid.UUID | None = None
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    expected_score: str
    expected_goals: dict
    confidence: float
    reasoning: str = ""
    created_at: dt.datetime | None = None


class PredictionResultIn(BaseModel):
    prediction_id: uuid.UUID
    home_score: int
    away_score: int


# --- Content opportunity ---
class OpportunityItemIn(BaseModel):
    title: str
    topic: str | None = None
    source_kind: str = "news"
    content_type: str | None = None
    status: str | None = None
    signals: dict = Field(default_factory=dict)
    meta: dict = Field(default_factory=dict)


class OpportunityOut(BaseModel):
    opportunity_id: uuid.UUID | None = None
    title: str
    topic: str
    score: float
    urgency: str
    content_type: str
    target_platforms: list[str] = Field(default_factory=list)
    estimated_reach: int = 0
    estimated_value: float = 0.0


# --- Executive ---
class DecisionCandidateIn(BaseModel):
    title: str
    topic: str | None = None
    source_kind: str = "news"
    status: str | None = None
    signals: dict = Field(default_factory=dict)


class ExecutiveDecisionOut(BaseModel):
    decision_id: uuid.UUID | None = None
    title: str
    topic: str
    priority_level: str
    opportunity_score: float
    recommendation: dict = Field(default_factory=dict)
    reasoning: str = ""
    urgency: str
    expected_reach: int = 0
    expected_engagement: float = 0.0
    task_ids: list[str] = Field(default_factory=list)
