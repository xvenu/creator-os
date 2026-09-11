"""Campaign Intelligence Agent (NEW): discover → evaluate → rank → persist → memory."""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.core.logging import get_logger
from app.db.models.phase2 import Campaign, CampaignOpportunity
from app.services import campaign_service as svc
from app.services import memory_service

log = get_logger("agent.campaign_intelligence")

_session_factory: Callable | None = None


def set_session_factory(factory: Callable | None) -> None:
    global _session_factory
    _session_factory = factory


def _resolve_factory() -> Callable:
    if _session_factory is not None:
        return _session_factory
    from app.core.config import get_settings
    from app.db.session import get_session_factory

    return get_session_factory(get_settings())


class CampaignIntelligenceAgent(BaseAgent):
    metadata = AgentMetadata(
        name="campaign_intelligence",
        description="Discover clipping campaigns, rank profitability, recommend opportunities",
        version="0.2.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        listings: list[dict] = list(ctx.payload.get("listings", []))
        if "campaign_name" in ctx.payload:
            listings.append(ctx.payload)
        if not listings:
            return {"discovered": 0, "opportunities": []}

        campaigns = svc.discover_campaigns(listings)
        ranked = svc.rank_opportunities(campaigns)

        factory = _resolve_factory()
        out: list[dict] = []
        async with factory() as session:
            for opp in ranked:
                stmt = select(Campaign).where(Campaign.campaign_name == opp["campaign_name"])
                campaign_row = (await session.execute(stmt)).scalar_one_or_none()
                if campaign_row is None:
                    campaign_row = Campaign(
                        campaign_name=opp["campaign_name"],
                        platform=opp["platform"],
                        payout_model=opp["payout_model"],
                        payout_estimate=opp["payout_estimate"],
                        requirements=opp["requirements"],
                        niche=opp["niche"],
                        active=opp["active"],
                        countries=ctx.payload.get("countries", []),
                        meta={},
                    )
                    session.add(campaign_row)
                    await session.flush()
                else:
                    campaign_row.platform = opp["platform"]
                    campaign_row.payout_model = opp["payout_model"]
                    campaign_row.payout_estimate = opp["payout_estimate"]
                    campaign_row.requirements = opp["requirements"]
                    campaign_row.niche = opp["niche"]
                    campaign_row.active = opp["active"]
                    await session.flush()

                opp_row = CampaignOpportunity(
                    campaign_id=campaign_row.id,
                    campaign_name=opp["campaign_name"],
                    platform=opp["platform"],
                    score=opp["score"],
                    roi_estimate=opp["roi_estimate"],
                    risk_score=opp["risk_score"],
                    payout_estimate=opp["payout_estimate"],
                    rationale=opp["rationale"],
                    recommended=opp["recommended"],
                    meta={"niche": opp["niche"]},
                )
                session.add(opp_row)
                await session.flush()
                if opp["recommended"]:
                    await memory_service.observe_campaign(
                        session,
                        opp["campaign_name"],
                        extra={"platform": opp["platform"], "score": opp["score"]},
                    )
                out.append(
                    {
                        "campaign_name": opp["campaign_name"],
                        "platform": opp["platform"],
                        "payout_model": opp["payout_model"],
                        "payout_estimate": opp["payout_estimate"],
                        "requirements": opp["requirements"],
                        "niche": opp["niche"],
                        "active": opp["active"],
                        "score": opp["score"],
                        "roi_estimate": opp["roi_estimate"],
                        "risk_score": opp["risk_score"],
                        "recommended": opp["recommended"],
                    }
                )
            await session.commit()

        log.info("campaign_intelligence_done", discovered=len(out))
        return {"discovered": len(out), "opportunities": out}
