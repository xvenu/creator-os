"""Canonical agent roster — Creator-OS pulse edition.

Video production belongs exclusively to the Zoza Video Factory.
FootballPulse is a Zoza client (see app.modules.zoza_client) and owns
intelligence → packages → publishing → analytics → revenue → learning.
"""
from __future__ import annotations

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.agents.registry import registry


def _make_agent(name: str, description: str) -> type[BaseAgent]:
    _metadata = AgentMetadata(name=name, description=description)

    class _StubAgent(BaseAgent):
        metadata = _metadata

        async def handle(self, ctx: AgentContext) -> dict:
            return {"message": f"{self.name} stub executed", "payload_keys": list(ctx.payload.keys())}

    _StubAgent.__name__ = "".join(p.capitalize() for p in name.split("_")) + "Agent"
    _StubAgent.__qualname__ = _StubAgent.__name__
    return _StubAgent


# Agents with real Phase 2+ implementations: name -> import path.
REAL_AGENTS: dict[str, str] = {
    "news_intelligence": "app.agents.news_agent:NewsIntelligenceAgent",
    "match_analysis": "app.agents.match_agent:MatchAnalysisAgent",
    "transfer_intelligence": "app.agents.transfer_agent:TransferIntelligenceAgent",
    "campaign_intelligence": "app.agents.campaign_agent:CampaignIntelligenceAgent",
    "prediction": "app.agents.prediction_agent:PredictionAgent",
    "executive": "app.agents.executive_agent:ExecutiveAgent",
    "content_opportunity": "app.agents.opportunity_agent:ContentOpportunityAgent",
    "research": "app.agents.research_agent:ResearchAgent",
    "content_planner": "app.agents.planner_agent:ContentPlannerAgent",
    "script_writer": "app.agents.script_agent:ScriptWriterAgent",
    "seo": "app.agents.seo_agent:SEOAgent",
    "thumbnail_strategy": "app.agents.thumbnail_agent:ThumbnailStrategyAgent",
    "region_intelligence": "app.agents.region_agent:RegionIntelligenceAgent",
    "packaging": "app.agents.packaging_agent:PackagingAgent",
    "zoza_dispatcher": "app.modules.zoza_client.agent:ZozaDispatcherAgent",
}

AGENT_SPECS: list[tuple[str, str]] = [
    ("news_intelligence", "Collect, deduplicate, rank and detect breaking football news"),
    ("match_analysis", "Analyze matches, tactics, talking points and trends"),
    ("transfer_intelligence", "Track rumors, score credibility, estimate probabilities"),
    ("campaign_intelligence", "Discover clipping campaigns, rank profitability, recommend opportunities"),
    ("prediction", "Generate match predictions, probabilities and scorelines"),
    ("executive", "CEO: evaluate opportunities, decide production, generate content tasks"),
    ("content_opportunity", "Convert intelligence into scored content opportunities"),
    ("research", "Aggregate intelligence into enriched research briefs"),
    ("content_planner", "Build content calendars: what, when, platforms, priority"),
    ("script_writer", "Write retention-optimized scripts with quality gating"),
    ("seo", "Generate titles, descriptions, keywords and hashtags"),
    ("thumbnail_strategy", "Generate thumbnail concepts: text, visuals, emotion, color"),
    ("region_intelligence", "Rank regions by monetization; recommend language and timing"),
    ("packaging", "Assemble publish-ready content packages + rollout strategies"),
    ("zoza_dispatcher", "Submit packages to Zoza factory, track jobs, collect exports"),
    ("fact_verification", "Validate claims, detect hallucinations, flag uncertainty"),
    ("video_production", "DEPRECATED stub — production is Zoza-owned; see zoza_dispatcher"),
    ("publisher", "Publish to YouTube, TikTok, Instagram, X, Telegram"),
    ("analytics", "Track CTR, retention, engagement, subscriber growth"),
    ("learning", "Learn from performance and update content strategy"),
]

CANONICAL_PHASE1_AGENTS = [
    "news_intelligence",
    "match_analysis",
    "transfer_intelligence",
    "prediction",
    "research",
    "script_writer",
    "fact_verification",
    "content_planner",
    "video_production",
    "publisher",
    "analytics",
    "learning",
]


def _load_real_agent(name: str) -> BaseAgent | None:
    path = REAL_AGENTS.get(name)
    if not path:
        return None
    module_path, class_name = path.split(":")
    import importlib

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()


def register_all_agents() -> None:
    for name, desc in AGENT_SPECS:
        if name in registry.names():
            continue
        real = _load_real_agent(name)
        if real is not None:
            registry.register(real)
        else:
            registry.register(_make_agent(name, desc)())


def get_agent_names() -> list[str]:
    return [n for n, _ in AGENT_SPECS]
