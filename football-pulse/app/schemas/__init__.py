"""Domain schemas re-export."""
from app.schemas.domain import MemoryIn, MemoryOut, NewsIn, NewsOut, PredictionIn, TaskIn, TaskOut
from app.schemas.intelligence import (
    CampaignInput,
    CampaignIntelOut,
    MatchAnalysisOut,
    MatchAnalysisRequest,
    NewsClusterOut,
    NewsIntelOut,
    RawArticle,
    RumorInput,
    TeamFormInput,
    TransferIntelOut,
)

from app.schemas.decisions import (
    DecisionCandidateIn,
    ExecutiveDecisionOut,
    OpportunityItemIn,
    OpportunityOut,
    PredictionMatchRequest,
    PredictionOut,
    PredictionResultIn,
)
from app.schemas.content import (
    BriefJobIn,
    PackageJobIn,
    ScriptJobIn,
    SEOJobIn,
    ThumbnailJobIn,
)

__all__ = [
    "BriefJobIn",
    "CampaignInput",
    "CampaignIntelOut",
    "DecisionCandidateIn",
    "ExecutiveDecisionOut",
    "MatchAnalysisOut",
    "MatchAnalysisRequest",
    "MemoryIn",
    "MemoryOut",
    "NewsClusterOut",
    "NewsIn",
    "NewsIntelOut",
    "NewsOut",
    "OpportunityItemIn",
    "OpportunityOut",
    "PackageJobIn",
    "PredictionIn",
    "PredictionMatchRequest",
    "PredictionOut",
    "PredictionResultIn",
    "RawArticle",
    "RumorInput",
    "ScriptJobIn",
    "SEOJobIn",
    "TaskIn",
    "TaskOut",
    "TeamFormInput",
    "ThumbnailJobIn",
    "TransferIntelOut",
]
