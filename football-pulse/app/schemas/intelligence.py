"""Phase 2 Pydantic schemas — intelligence I/O contracts."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


# --- News intelligence ---
class RawArticle(BaseModel):
    title: str
    source: str
    url: str
    body: str | None = None
    published_at: dt.datetime | None = None


class NewsIntelOut(BaseModel):
    title: str
    summary: str
    source: str
    url: str
    published_at: dt.datetime | None = None
    importance_score: float = Field(ge=0.0, le=1.0, default=0.0)
    breaking_news: bool = False
    entities: dict = Field(default_factory=dict)
    content_hash: str = ""
    id: uuid.UUID | None = None


class NewsClusterOut(BaseModel):
    id: uuid.UUID | None = None
    title: str
    story_key: str
    article_count: int = 0
    trend_score: float = 0.0
    importance_score: float = 0.0
    is_breaking: bool = False


# --- Match analysis ---
class TeamFormInput(BaseModel):
    club: str
    last_results: list[str] = Field(default_factory=list)  # "W" | "D" | "L"
    goals_for: int = 0
    goals_against: int = 0


class MatchAnalysisRequest(BaseModel):
    match_id: uuid.UUID | None = None
    home_club: str
    away_club: str
    league: str | None = None
    status: str = "upcoming"  # upcoming | completed
    home_score: int | None = None
    away_score: int | None = None
    events: list[dict] = Field(default_factory=list)
    home_form: TeamFormInput | None = None
    away_form: TeamFormInput | None = None


class MatchAnalysisOut(BaseModel):
    id: uuid.UUID | None = None
    match_id: uuid.UUID | None = None
    key_events: list[dict] = Field(default_factory=list)
    tactical_summary: str = ""
    standout_players: list[dict] = Field(default_factory=list)
    strengths: dict = Field(default_factory=dict)
    weaknesses: dict = Field(default_factory=dict)
    narrative: str = ""
    generated_at: dt.datetime | None = None


# --- Transfer intelligence ---
class RumorInput(BaseModel):
    player: str
    from_club: str | None = None
    to_club: str | None = None
    sources: list[str] = Field(default_factory=list)
    status: str = "rumor"


class TransferIntelOut(BaseModel):
    id: uuid.UUID | None = None
    player: str
    from_club: str | None = None
    to_club: str | None = None
    status: str = "rumor"
    credibility_score: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    probability: float = Field(ge=0.0, le=1.0, default=0.0)
    sources: list[str] = Field(default_factory=list)
    last_updated: dt.datetime | None = None


# --- Campaign intelligence ---
class CampaignInput(BaseModel):
    campaign_name: str
    platform: str
    payout_model: str = "rev_share"
    payout_estimate: float = 0.0
    requirements: dict = Field(default_factory=dict)
    niche: str = "football"
    active: bool = True
    countries: list[str] = Field(default_factory=list)
    url: str | None = None


class CampaignIntelOut(BaseModel):
    id: uuid.UUID | None = None
    campaign_name: str
    platform: str
    payout_model: str
    payout_estimate: float = 0.0
    requirements: dict = Field(default_factory=dict)
    niche: str = "football"
    active: bool = True
    score: float = Field(ge=0.0, le=1.0, default=0.0)
    roi_estimate: float = 0.0
    risk_score: float = Field(ge=0.0, le=1.0, default=0.0)
    recommended: bool = False
    rationale: str = ""
