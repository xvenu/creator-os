"""Phase 4 API: acquisition, network, assets, prediction, breakouts,
monetization, revenue-execution, forecasting, products."""
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(tags=["phase4"])


# ---------- Acquisition ----------
class SnapshotIn(BaseModel):
    channel: str
    node: str = "global"
    followers: int = 0
    subscribers: int = 0
    traffic: int = 0
    conversions: int = 0
    spend: float = 0.0


class EventIn(BaseModel):
    event_type: str
    channel: str = ""
    node: str = "global"
    count: int = 0
    cost: float = 0.0


@router.post("/acquisition/snapshot", summary="Record audience snapshot")
def acq_snapshot(payload: SnapshotIn, db: Session = Depends(get_db)):
    from app.modules.acquisition.engine import AudienceAcquisitionEngine
    return {"id": AudienceAcquisitionEngine.record_snapshot(db, **payload.model_dump()).id}


@router.post("/acquisition/event", summary="Record acquisition event")
def acq_event(payload: EventIn, db: Session = Depends(get_db)):
    from app.modules.acquisition.engine import AudienceAcquisitionEngine
    return {"id": AudienceAcquisitionEngine.record_event(db, **payload.model_dump()).id}


@router.get("/acquisition/report", summary="Growth reports + forecasts")
def acq_report(node: str = "global", db: Session = Depends(get_db)):
    from app.modules.acquisition.engine import (growth_report, acquisition_recommendations,
                                                audience_forecast)
    return {"report": growth_report(db, node),
            "recommendations": acquisition_recommendations(db, node),
            "forecast": audience_forecast(db, node)}


# ---------- Network / orchestrator ----------
class NodeIn(BaseModel):
    name: str
    kind: str
    parent: str = ""
    region: str = "US"


@router.post("/network/nodes", summary="Register network node")
def net_add(payload: NodeIn, db: Session = Depends(get_db)):
    from app.modules.network.engine import register_node
    return {"id": register_node(db, **payload.model_dump()).id}


@router.get("/network", summary="Network management: nodes + allocation + conflicts")
def net_view(db: Session = Depends(get_db)):
    from app.modules.network.engine import nodes, seed_default_network
    from app.modules.orchestrator.engine import network_plan
    seed_default_network(db)
    return {"nodes": nodes(db), "plan": network_plan(db)}


# ---------- Assets ----------
class AssetIn(BaseModel):
    name: str
    kind: str
    traffic: int = 0
    revenue: float = 0.0
    growth: float = 0.0
    engagement: float = 0.0


@router.post("/assets", summary="Register owned asset")
def asset_add(payload: AssetIn, db: Session = Depends(get_db)):
    from app.modules.assets.engine import register_asset
    return {"id": register_asset(db, **payload.model_dump()).id}


@router.get("/assets", summary="Asset performance + valuation + expansion")
def asset_view(db: Session = Depends(get_db)):
    from app.modules.assets.engine import (performance_report, valuation_report,
                                           expansion_opportunities)
    return {"performance": performance_report(db),
            "valuation": valuation_report(db),
            "expansion": expansion_opportunities(db)}


# ---------- Prediction / breakouts ----------
@router.post("/prediction/{ptype}", summary="Forecast artist|song|genre|market (7|30|90d)")
def predict(ptype: str, subject: str, horizon_days: int = 30, db: Session = Depends(get_db)):
    from app.modules.prediction.engine import (ArtistPredictor, TrendPredictor,
                                               GenrePredictor, MarketPredictor)
    cls = {"artist": ArtistPredictor, "song": TrendPredictor,
           "genre": GenrePredictor, "market": MarketPredictor}.get(ptype)
    if cls is None:
        raise ValueError("ptype must be artist|song|genre|market")
    return cls.forecast(db, subject, horizon_days)


@router.get("/prediction/report", summary="Forecast reports")
def predict_report(horizon_days: int = 30, db: Session = Depends(get_db)):
    from app.modules.prediction.engine import forecast_report
    return {"forecasts": forecast_report(db, horizon_days)}


@router.post("/breakouts/scan", summary="Run breakout detection")
def bo_scan(db: Session = Depends(get_db)):
    from app.modules.breakout.engine import scan
    return {"alerts": scan(db, actor="api")}


@router.get("/breakouts", summary="Breakout watchlists + recommendations")
def bo_view(db: Session = Depends(get_db)):
    from app.modules.breakout.engine import watchlist, executive_recommendations
    return {"watchlist": watchlist(db), "recommendations": executive_recommendations(db)}


# ---------- Monetization / revenue-execution ----------
class RuleIn(BaseModel):
    name: str
    rule_type: str
    config: dict = {}


@router.post("/monetization/rules", summary="Upsert monetization rule")
def mon_rule(payload: RuleIn, db: Session = Depends(get_db)):
    from app.modules.monetization.engine import upsert_rule
    return {"id": upsert_rule(db, payload.name, payload.rule_type, payload.config).id}


@router.get("/monetization/match", summary="Match sponsors + price inventory")
def mon_match(genre: str = "Pop", country: str = "US", sponsor_id: int = 0,
              db: Session = Depends(get_db)):
    from app.modules.monetization.engine import (SponsorMatcher, PricingEngine,
                                                 AffiliateOptimizer, InventoryManager,
                                                 CampaignAllocator)
    out = {"matches": SponsorMatcher.match(db, genre, country),
           "pricing": PricingEngine.price(db, "sponsored_feature", genre, country),
           "affiliates": AffiliateOptimizer.select(genre),
           "inventory": InventoryManager.utilization(db)}
    if sponsor_id:
        out["allocation"] = CampaignAllocator.allocate(db, sponsor_id, genre, country)
    return out


@router.get("/revenue-execution", summary="Revenue actions + forecasts + utilization")
def rex_view(db: Session = Depends(get_db)):
    from app.modules.revenue_execution.engine import (plan_actions, active_campaigns,
                                                      utilization, forecast)
    return {"planned": plan_actions(db, actor="api"),
            "active": active_campaigns(db), "utilization": utilization(db),
            "forecast": forecast(db)}


@router.post("/revenue-execution/{aid}/execute", summary="Execute a revenue action")
def rex_exec(aid: int, campaign_id: int = 0, db: Session = Depends(get_db)):
    from app.modules.revenue_execution.engine import execute_action
    return {"id": execute_action(db, aid, campaign_id, actor="api").id}


# ---------- Forecasting ----------
@router.post("/forecasting", summary="Executive forecasts (weekly|monthly|quarterly|annual)")
def fc_gen(scope: str = "revenue", horizon: str = "monthly", db: Session = Depends(get_db)):
    from app.modules.forecasting.engine import generate
    return generate(db, scope, horizon, actor="api")


@router.get("/forecasting", summary="Latest forecast")
def fc_view(scope: str = "revenue", horizon: str = "monthly", db: Session = Depends(get_db)):
    from app.modules.forecasting.engine import latest
    return {"forecast": latest(db, scope, horizon)}


# ---------- Products ----------
class ProductIn(BaseModel):
    name: str
    kind: str
    price: float = 0.0


@router.post("/products", summary="Add digital product")
def prod_add(payload: ProductIn, db: Session = Depends(get_db)):
    from app.modules.products.engine import add_product
    return {"id": add_product(db, **payload.model_dump()).id}


@router.post("/products/{pid}/sale", summary="Record product sale")
def prod_sale(pid: int, amount: float = 0.0, db: Session = Depends(get_db)):
    from app.modules.products.engine import record_sale
    return {"id": record_sale(db, pid, amount).id}


@router.get("/products", summary="Product performance")
def prod_view(db: Session = Depends(get_db)):
    from app.modules.products.engine import performance, totals
    return {"products": performance(db), "totals": totals(db)}


# ---------- Autonomy v4 ----------
@router.post("/autonomy/cycle-v4", summary="Extended growth+monetization loop cycle")
def auto_v4(db: Session = Depends(get_db)):
    from app.modules.autonomy.engine import run_cycle_v4
    return run_cycle_v4(db, actor="api")
