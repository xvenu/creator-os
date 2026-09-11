import pytest
from app.modules.executive.engine import (
    ExecutiveAgent, generate_strategy, latest_strategy, set_goal,
    update_goal_progress, goals,
)
from app.modules.director.engine import build_directives, execute_directives
from app.modules.revenue_optimizer.engine import optimize, results
from app.modules.warroom.engine import briefing, attack_strategies
from app.modules.autonomy.engine import (
    run_cycle, cycles, activity_feed, emergency_stop, executive_override, is_running,
)


def _seed(db):
    from app.modules.market_intelligence.engine import record_country_trend
    from app.modules.profitability.engine import record_genre_analytic
    from app.modules.discovery.engine import upsert_artist
    from app.modules.competitors.engine import record_competitor
    record_country_trend(db, "US", "Banger", artist="Nova", score=80.0, genre="Pop")
    record_genre_analytic(db, "Pop", "US", views=1000, engagement=300, posts=5)
    upsert_artist(db, "Nova", genre="Pop", followers=60_000, velocity=1.5)
    record_competitor(db, "Billboard", post_count=30, engagement_est=100,
                      topics=["afrobeats", "charts"])


def test_goals_and_strategy(db):
    g = set_goal(db, "10k views", "growth", target=10000.0)
    assert goals(db)[0]["progress"] == 0.0
    update_goal_progress(db, g.id, 10000.0)
    assert goals(db)[0]["status"] == "achieved"
    with pytest.raises(ValueError):
        set_goal(db, "bad", "vibes")
    with pytest.raises(ValueError):
        update_goal_progress(db, 99999, 1.0)
    with pytest.raises(ValueError):
        generate_strategy(db, "decade")
    for h in ("daily", "weekly", "monthly"):
        s = generate_strategy(db, h)
        assert {"markets", "genres", "posting_volume", "revenue_target"} <= set(s)
    assert latest_strategy(db, "daily")["horizon"] == "daily"


def test_executive_run(db):
    _seed(db)
    out = ExecutiveAgent.run(db)
    assert {"snapshot", "strategy", "allocation", "focus"} <= set(out)
    assert out["strategy"]["id"] is not None


def test_director_flow(db):
    _seed(db)
    ExecutiveAgent.run(db)
    ds = build_directives(db, max_items=3)
    assert 0 < len(ds) <= 3 and {"kind", "topic", "market"} <= set(ds[0])
    done = execute_directives(db, ds)
    assert all(d["status"] == "queued" for d in done)
    # policy-blocked content never publishes
    blocked = execute_directives(db, [{"kind": "news", "topic": "election campaign rally",
                                       "genre": "Pop", "market": "US"}])
    assert blocked[0]["status"] == "blocked"


def test_optimizer_warroom(db):
    _seed(db)
    recs = optimize(db)
    assert {r["scope"] for r in recs} >= {"mrr", "sponsorship", "affiliate"}
    assert len(results(db)) >= 3
    b = briefing(db)
    assert {"frequency", "gaps", "weaknesses", "opportunities"} <= set(b)
    assert attack_strategies(db)[0]["confidence"] > 0


def test_autonomy_cycle_and_safety(db):
    _seed(db)
    out = run_cycle(db)
    assert out["status"] == "completed" and len(out["stages"]) == 9
    assert cycles(db)[0]["status"] == "completed"
    assert len(activity_feed(db)) > 0
    # emergency stop halts; override resumes
    emergency_stop(db, "test", actor="test")
    assert is_running() is False
    assert run_cycle(db)["status"] == "skipped"
    executive_override(db, "resume", actor="test")
    assert is_running() is True
    out2 = run_cycle(db)
    assert out2["status"] in ("completed", "failed")
    with pytest.raises(ValueError):
        executive_override(db, "self-destruct")
