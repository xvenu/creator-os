import pytest
from app.modules.breakout.engine import scan, watchlist, acknowledge, executive_recommendations
from app.modules.monetization.engine import (SponsorMatcher, PricingEngine, AffiliateOptimizer,
                                             InventoryManager, CampaignAllocator, upsert_rule)
from app.modules.revenue_execution.engine import (plan_actions, execute_action, active_campaigns,
                                                  utilization, forecast)
from app.modules.orchestrator.engine import (detect_overlap, detect_duplication, resolve_conflicts,
                                             network_plan)
from app.modules.forecasting.engine import generate, latest
from app.modules.products.engine import add_product, record_sale, performance, totals


def _seed(db):
    from app.modules.discovery.engine import upsert_artist
    from app.modules.market_intelligence.engine import record_country_trend
    from app.modules.sponsorships.engine import create_sponsor
    upsert_artist(db, "Nova", genre="Pop", followers=200_000, velocity=3.0)
    for c in ("US", "UK", "CA"):
        record_country_trend(db, c, "Global Banger", artist="Nova", score=200.0)
    return create_sponsor(db, "Acme", actor="test").id


def test_breakout(db):
    _seed(db)
    alerts = scan(db)
    assert any(a["kind"] == "artist" for a in alerts)
    wl = watchlist(db)
    assert wl and wl[0]["signal"] >= 2.0
    acknowledge(db, wl[0]["id"])
    assert watchlist(db) == [w for w in watchlist(db, limit=100)]
    recs = executive_recommendations(db)
    assert recs and "priority" in recs[0]
    with pytest.raises(ValueError):
        acknowledge(db, 99999)


def test_monetization(db):
    sid = _seed(db)
    assert SponsorMatcher.match(db, "Pop")[0]["name"] == "Acme"
    p = PricingEngine.price(db, "sponsored_feature", "Pop", "US")
    assert p["price"] > 0 and "rationale" in p
    assert AffiliateOptimizer.select("Pop")[0]["payout"] > 0
    inv = InventoryManager.utilization(db)
    assert inv["capacity"] == 10
    alloc = CampaignAllocator.allocate(db, sid, "Pop", "US")
    assert alloc["campaign_id"] > 0
    upsert_rule(db, "prefer-pop", "sponsor_match", {"genre": "Pop"})
    with pytest.raises(ValueError):
        upsert_rule(db, "bad", "alchemy")


def test_revenue_execution(db):
    from app.modules.revenue_optimizer.engine import optimize
    _seed(db)
    optimize(db)
    planned = plan_actions(db)
    assert planned
    row = execute_action(db, 1)
    assert row.status == "executed"
    assert active_campaigns(db) == []
    u = utilization(db)
    assert {"campaigns", "utilization"} <= set(u)
    assert "projection" in forecast(db)
    with pytest.raises(ValueError):
        execute_action(db, 99999)


def test_orchestrator(db):
    from app.modules.network.engine import seed_default_network
    seed_default_network(db)
    assert detect_overlap(db)  # Hip-Hop + Pop share parent/region
    dups = detect_duplication({"A": ["Pop Hit"], "B": ["pop hit"]})
    assert dups[0]["topic"] == "pop hit"
    assert resolve_conflicts(db)
    plan = network_plan(db)
    assert {"allocation", "overlaps", "resolutions"} <= set(plan)


def test_forecasting_products(db):
    f = generate(db, "revenue", "monthly")
    assert len(f["projection"]) == 4 and f["risks"]
    assert latest(db, "revenue", "monthly")["scope"] == "revenue"
    assert generate(db, "growth", "weekly")["horizon"] == "weekly"
    with pytest.raises(ValueError):
        generate(db, "weather", "monthly")
    with pytest.raises(ValueError):
        generate(db, "revenue", "epoch")
    p = add_product(db, "Trend Report Q3", "report", price=49.0)
    record_sale(db, p.id, 49.0)
    record_sale(db, p.id, 49.0, retained=False)
    perf = performance(db)
    assert perf[0] == {"id": p.id, "name": "Trend Report Q3", "kind": "report",
                       "sales": 2, "revenue": 98.0, "retention": 0.5}
    assert totals(db) == {"sales": 2, "revenue": 98.0}
    with pytest.raises(ValueError):
        add_product(db, "x", "spaceship")
    with pytest.raises(ValueError):
        record_sale(db, 99999, 1.0)
