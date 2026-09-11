import pytest
from app.modules.acquisition.engine import (
    AudienceAcquisitionEngine as AAE, FollowerGrowthTracker, SubscriberGrowthTracker,
    TrafficGrowthTracker, ConversionAnalyzer, growth_report,
    acquisition_recommendations, audience_forecast,
)
from app.modules.network.engine import register_node, seed_default_network, nodes, allocate_resources
from app.modules.assets.engine import (register_asset, update_asset, performance_report,
                                        valuation_report, expansion_opportunities)
from app.modules.prediction.engine import (TrendPredictor, ArtistPredictor, GenrePredictor,
                                            MarketPredictor, forecast_report)


def test_acquisition_metrics(db):
    E = AAE.record_event
    E(db, "visit", count=1000, node="global")
    E(db, "convert", count=50, node="global")
    AAE.record_snapshot(db, "social", followers=1000, subscribers=100,
                        traffic=5000, conversions=50)
    AAE.record_snapshot(db, "social", followers=1700, subscribers=170,
                        traffic=6000, conversions=70)
    assert FollowerGrowthTracker.per_day(db) >= 0
    assert SubscriberGrowthTracker.per_day(db) >= 0
    assert isinstance(TrafficGrowthTracker.rate(db), float)
    f = ConversionAnalyzer.funnel(db)
    assert f == {"visits": 1000, "conversions": 50, "conversion_rate": 0.05,
                 "cpa": 0.0, "ltv": 125.0, "by_type": {"visit": 1000, "convert": 50}}
    rep = growth_report(db)
    assert {"followers_per_day", "funnel"} <= set(rep)
    assert acquisition_recommendations(db)
    assert audience_forecast(db, days=30)["days"] == 30
    with pytest.raises(ValueError):
        E(db, "teleport", count=1)


def test_network(db):
    assert seed_default_network(db) == 7
    assert seed_default_network(db) == 0  # idempotent
    assert len(nodes(db)) == 7
    assert len(nodes(db, kind="brand")) == 4
    with pytest.raises(ValueError):
        register_node(db, "X", "planet")
    plan = allocate_resources(db)
    assert plan["per_node"] >= 1 and "growth_allocation" in plan


def test_assets(db):
    a = register_asset(db, "pulse.com", "website", traffic=10000, revenue=500.0,
                       growth=0.2, engagement=0.5)
    assert a.valuation > 500 * 12
    update_asset(db, a.id, traffic=20000)
    assert performance_report(db)[0]["name"] == "pulse.com"
    v = valuation_report(db)
    assert v["total_valuation"] > 0
    assert expansion_opportunities(db)[0]["asset"] == "pulse.com"
    with pytest.raises(ValueError):
        register_asset(db, "x", "moon")
    with pytest.raises(ValueError):
        update_asset(db, 99999, traffic=1)


def test_prediction(db):
    from app.modules.market_intelligence.engine import record_country_trend
    from app.modules.profitability.engine import record_genre_analytic
    record_country_trend(db, "US", "Future Hit", artist="Nova", score=120.0)
    record_genre_analytic(db, "Pop", "US", views=2000, engagement=400)
    s = TrendPredictor.forecast(db, "Future Hit", 7)
    assert {"confidence", "opportunity", "rationale"} <= set(s)
    assert ArtistPredictor.forecast(db, "Nova", 30)["rationale"]
    assert GenrePredictor.forecast(db, "Pop", 90)["opportunity"] >= 0
    assert MarketPredictor.forecast(db, "US", 30)["subject"] == "US"
    assert forecast_report(db, 7)[0]["subject"] == "Future Hit"
    with pytest.raises(ValueError):
        TrendPredictor.forecast(db, "X", 365)
