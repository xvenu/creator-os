import pytest
from app.modules.memory.engine import store, search, record_outcome, lessons, history
from app.modules.policy.engine import check_content, events, is_safe_text
from app.modules.decision.engine import evaluate, decide_focus, decisions, record_decision_outcome
from app.modules.allocation.engine import score_all, priority_queue, allocate


def test_memory_store_search_lessons(db):
    store(db, "lesson", "Pop shorts win", "short captions beat articles", score=0.9)
    store(db, "decision", "Chose Pop", actor="test")
    assert any(r["title"] == "Pop shorts win" for r in search(db, "shorts"))
    assert any(r["kind"] == "decision" for r in search(db, "", kind="decision"))
    assert lessons(db)[0]["title"] == "Pop shorts win"
    record_outcome(db, "decision", "1", True, "worked", score=1.0)
    assert len(history(db)) >= 3
    with pytest.raises(ValueError):
        store(db, "dream", "x")


def test_policy_pass_block(db):
    ok = check_content(db, "New Pop Hit", "A catchy summer anthem", content_ref="t1")
    assert ok == {"allowed": True, "rule": None}
    bad = check_content(db, "Vote for X", "election campaign rally news", content_ref="t2")
    assert bad["allowed"] is False and bad["rule"] == "no_politics"
    assert is_safe_text("hello", "world") is True
    assert is_safe_text("vote for", "election") is False
    assert len(events(db)) >= 2
    assert events(db, verdict="block")[0]["rule"] == "no_politics"


def test_decision_evaluate_and_outcome(db):
    store(db, "success", "Pop strategy worked", score=0.8)
    out = evaluate(db, "Hip-Hop or Pop?",
                   [{"name": "Hip-Hop", "signals": {"profit": 40}},
                    {"name": "Pop", "signals": {"profit": 90}}])
    assert out["chosen"] == "Pop" and "consulted" in out["rationale"]
    assert decisions(db)[0]["question"] == "Hip-Hop or Pop?"
    record_decision_outcome(db, out["id"], "success")
    assert decisions(db)[0]["outcome"] == "success"
    with pytest.raises(ValueError):
        record_decision_outcome(db, 99999, "success")
    with pytest.raises(ValueError):
        record_decision_outcome(db, out["id"], "maybe")


def test_decide_focus_live(db):
    from app.modules.profitability.engine import record_genre_analytic
    from app.modules.market_intelligence.engine import record_country_trend
    record_genre_analytic(db, "Pop", "US", views=1000, engagement=300)
    record_genre_analytic(db, "Hip-Hop", "US", views=100, engagement=5)
    record_country_trend(db, "US", "Hit", artist="A", score=90.0)
    focus = decide_focus(db)
    assert focus["genre"]["chosen"] == "Pop"
    assert focus["market"]["chosen"] in ("US", "CA", "UK", "AU", "DE")


def test_allocation_flow(db):
    from app.modules.market_intelligence.engine import record_country_trend
    from app.modules.profitability.engine import record_genre_analytic
    record_country_trend(db, "US", "Banger", artist="Nova", score=80.0, genre="Pop")
    record_genre_analytic(db, "Pop", "US", views=500, engagement=100)
    scored = score_all(db)
    assert len(scored) > 0
    assert priority_queue(db, 3)[0]["impact"] >= priority_queue(db, 3)[-1]["impact"]
    alloc = allocate(db, top_n=2)
    assert len(alloc["allocated"]) == 2 and "genre_focus" in alloc
