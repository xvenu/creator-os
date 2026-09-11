"""Phase 4 tests: region engine, revenue scoring + Region Agent."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentStatus
from app.db.models import Memory
from app.db.models.phase4 import RegionIntelligence
from app.services import region_service as svc


def test_region_tiers_complete():
    tiers = {r: d["tier"] for r, d in svc.REGIONS.items()}
    for r in ("US", "UK", "Canada", "Australia", "Germany", "Netherlands", "Norway", "Switzerland"):
        assert tiers[r] == 1, r
    for r in ("France", "Belgium", "Austria", "Denmark", "Sweden", "Ireland"):
        assert tiers[r] == 2, r
    assert tiers["Brazil"] == 3


def test_monetization_ranking_prefers_premium():
    assert svc.monetization_score("US") > svc.monetization_score("India")
    assert 0.0 <= svc.monetization_score("UK") <= 1.0
    with pytest.raises(ValueError):
        svc.monetization_score("Atlantis")


def test_audience_quality_rewards_interest():
    assert svc.audience_quality("Brazil") > svc.audience_quality("Canada")


def test_rank_regions_includes_lower_tiers():
    top = svc.rank_regions(limit=8)
    assert len(top) == 8
    assert any(r["tier"] in (2, 3) for r in top)  # tier mix guaranteed
    comps = [r["composite_score"] for r in top]
    assert max(comps) == comps[0]  # best region still leads


def test_rank_regions_without_mix_is_sorted():
    top = svc.rank_regions(limit=8, ensure_tier_mix=False)
    scores = [r["composite_score"] for r in top]
    assert scores == sorted(scores, reverse=True)


def test_revenue_opportunity_formula():
    regions = [svc.score_region("US"), svc.score_region("India")]
    out = svc.revenue_opportunity(0.8, regions)
    us = next(r for r in regions if r["region"] == "US")
    expected = round(0.8 * us["monetization_score"] * us["audience_quality"], 4)
    assert out["revenue_opportunity_score"] == expected
    assert out["best_regions"][0] == "US"
    assert out["best_language"] and out["best_publish_time"]
    with pytest.raises(ValueError):
        svc.revenue_opportunity(0.8, [])


def test_executive_uses_revenue_signal():
    from app.services import executive_service as ex

    base = {"news_importance": 0.7, "transfer_credibility": 0.7,
            "prediction_confidence": 0.7, "campaign_roi": 0.7, "trend_score": 0.7}
    plain = ex.evaluate_opportunity(dict(base))
    boosted = ex.evaluate_opportunity({**base, "revenue_opportunity_score": 1.0})
    dragged = ex.evaluate_opportunity({**base, "revenue_opportunity_score": 0.0})
    assert boosted["opportunity_score"] > plain["opportunity_score"] > dragged["opportunity_score"]


def test_executive_unchanged_without_revenue_signal():
    from app.services import executive_service as ex

    signals = {"news_importance": 1.0, "transfer_credibility": 0.5,
               "prediction_confidence": 0.5, "campaign_roi": 0.5, "trend_score": 0.5}
    assert ex.evaluate_opportunity(signals)["opportunity_score"] == 0.625


async def test_region_agent_persists_and_memorizes(session_factory):
    from app.agents.region_agent import RegionIntelligenceAgent

    result = await RegionIntelligenceAgent().run(
        AgentContext(payload={"topic": "Arsenal record signing", "limit": 5}))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["analyzed"] == 1
    assert len(result.output["items"][0]["regions"]) == 5
    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(RegionIntelligence))).scalar() == 5
        best = (await session.execute(
            select(Memory).where(Memory.kind == "best_regions"))).scalars().all()
        assert len(best) >= 1  # monetizable regions memorized, lower tiers not ignored
        times = (await session.execute(
            select(Memory).where(Memory.kind == "best_publish_times"))).scalars().all()
        assert len(times) >= 1


def test_score_region_output_shape():
    scored = svc.score_region("UK")
    for key in ("region", "tier", "cpm_estimate", "rpm_estimate", "football_interest",
                "recommended_language", "recommended_publish_time",
                "monetization_score", "audience_quality", "composite_score"):
        assert key in scored, f"missing {key}"
    assert scored["recommended_language"] == "en"


def test_rank_regions_respects_limit():
    assert len(svc.rank_regions(limit=3)) == 3


async def test_low_monetization_region_not_memorized(session_factory):
    from app.services import memory_service

    async with session_factory() as session:
        await memory_service.observe_region_performance(session, "Nigeria", 0.2, "18:00 UTC", "T")
        from sqlalchemy import select
        from app.db.models import Memory
        best = (await session.execute(
            select(Memory).where(Memory.kind == "best_regions"))).scalars().all()
        assert best == []
