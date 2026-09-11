import pytest
from app.modules.revenue.engine import (
    record_revenue, mrr, revenue_by, revenue_trend, revenue_forecast,
    leaderboard, summary,
)


def test_revenue_flow(db):
    record_revenue(db, "sponsorship", 500.0, country="US", genre="Pop",
                   platform="telegram", actor="test")
    record_revenue(db, "affiliate", 200.0, country="UK", actor="test")
    s = summary(db)
    assert s["total"] == 700.0
    assert s["mrr"]["mrr_30d"] == 700.0
    assert s["by_country"][0]["key"] == "US"
    assert revenue_trend(db, 4)[-1]["total"] >= 700.0
    fc = revenue_forecast(db)
    assert len(fc["projection"]) == 4
    assert leaderboard(db, "source")[0]["key"] == "sponsorship"
    with pytest.raises(ValueError):
        record_revenue(db, "printing-money", 1.0)
    with pytest.raises(ValueError):
        revenue_by(db, "mood")
