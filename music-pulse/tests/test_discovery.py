import pytest
from app.modules.discovery.engine import (
    classify, upsert_artist, discovery_report, add_watchlist,
    watchlist, weekly_breakout_predictions,
)


def test_classify_thresholds():
    assert classify() == "Emerging"
    assert classify(followers=50_000, velocity=0.8) == "Rising"
    assert classify(followers=200_000, velocity=3.0) == "Breakout"
    assert classify(followers=5_000_000) == "Established"


def test_report_watchlist_breakout(db):
    a = upsert_artist(db, "Nova X", genre="Pop", followers=60_000, velocity=1.5)
    upsert_artist(db, "Old Star", followers=5_000_000)
    assert a.classification == "Rising"
    assert any(r["artist"] == "Nova X" for r in discovery_report(db, "Rising"))
    with pytest.raises(ValueError):
        discovery_report(db, "Superstar")
    add_watchlist(db, a.id, actor="test")
    assert any(w["artist"] == "Nova X" for w in watchlist(db))
    preds = weekly_breakout_predictions(db)
    assert preds[0]["artist"] == "Nova X" and "confidence" in preds[0]
    with pytest.raises(ValueError):
        add_watchlist(db, 99999)
