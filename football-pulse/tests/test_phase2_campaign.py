"""Phase 2 tests: CampaignService + Campaign Intelligence Agent."""
from __future__ import annotations

from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentStatus
from app.db.models import Memory
from app.db.models.phase2 import Campaign, CampaignOpportunity
from app.services import campaign_service as svc


def test_discover_sanitizes_listings():
    raw = [
        {"campaign_name": "  PremClip ", "platform": "TikTok", "payout_estimate": 500},
        {"campaign_name": "", "platform": "X"},
        {"campaign_name": "Weird Niche", "platform": "X", "niche": "crypto"},
    ]
    out = svc.discover_campaigns(raw)
    assert len(out) == 2
    assert out[0]["campaign_name"] == "PremClip"
    assert out[1]["niche"] == "general"  # unknown niche normalized


def test_normalize_niche():
    assert svc.normalize_niche("Football") == "football"
    assert svc.normalize_niche("crypto") == "general"


def test_risk_fixed_below_unknown_and_strictness_adds():
    low = svc.risk_score({"payout_model": "fixed", "requirements": {}, "countries": ["global"]})
    high = svc.risk_score({"payout_model": "unknown", "requirements": {}, "countries": ["global"]})
    assert low < high
    strict = svc.risk_score({
        "payout_model": "fixed",
        "requirements": {"min_followers": 50000, "exclusivity": True, "upfront_fee": True},
        "countries": ["US"],
    })
    assert strict > low


def test_roi_estimate_formula():
    campaign = {"payout_estimate": 1000.0, "niche": "football"}
    assert svc.roi_estimate(campaign, 0.2) == 800.0
    gaming = {"payout_estimate": 1000.0, "niche": "gaming"}
    assert svc.roi_estimate(gaming, 0.2) < 800.0


def test_score_campaign_recommends_good_active(sample_campaigns):
    good = svc.score_campaign(sample_campaigns[0])
    bad = svc.score_campaign(sample_campaigns[1])
    assert good["recommended"] is True
    assert bad["recommended"] is False
    assert good["score"] > bad["score"]
    for key in ("campaign_name", "platform", "payout_model", "payout_estimate",
                "requirements", "niche", "active", "score"):
        assert key in good, f"missing {key}"


def test_rank_opportunities_sorted_desc(sample_campaigns):
    ranked = svc.rank_opportunities(sample_campaigns)
    scores = [o["score"] for o in ranked]
    assert scores == sorted(scores, reverse=True)
    assert ranked[0]["campaign_name"] == "PremClip Pro"


async def test_campaign_agent_persists_and_memorizes(session_factory, sample_campaigns):
    from app.agents.campaign_agent import CampaignIntelligenceAgent

    agent = CampaignIntelligenceAgent()
    result = await agent.run(AgentContext(payload={"listings": sample_campaigns}))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["discovered"] == 2

    async with session_factory() as session:
        n_campaigns = (await session.execute(select(func.count()).select_from(Campaign))).scalar()
        n_opps = (await session.execute(select(func.count()).select_from(CampaignOpportunity))).scalar()
        assert n_campaigns == 2 and n_opps == 2
        mem = (await session.execute(
            select(Memory).where(
                Memory.kind == "recurring_campaign_opportunities",
                Memory.key == "premclip pro",
            )
        )).scalar_one_or_none()
        assert mem is not None  # recommended campaign memorized
