import pytest
from app.modules.profitability.engine import (
    GENRES, record_genre_analytic, profitability_score, leaderboard,
    revenue_opportunity, growth_forecast,
)


def test_genres_tracked():
    assert set(GENRES) == {"Hip-Hop", "Pop", "R&B", "Country", "EDM", "Latin",
                           "Rock", "Afrobeats", "K-Pop", "Indie"}


def test_score_and_leaderboard(db):
    record_genre_analytic(db, "Hip-Hop", "US", views=1000, engagement=300,
                          posts=12, retention=0.8, sponsorship_score=90.0)
    record_genre_analytic(db, "Rock", "US", views=100, engagement=2,
                          posts=1, retention=0.1, sponsorship_score=5.0)
    s = profitability_score(db, "Hip-Hop", "US")
    assert s["score"] > profitability_score(db, "Rock", "US")["score"]
    assert set(s["components"]) == {"engagement_rate", "growth", "sponsorship",
                                    "frequency", "retention"}
    board = leaderboard(db, "US")
    assert board[0]["genre"] == "Hip-Hop"
    opp = revenue_opportunity(db, "Hip-Hop")
    assert opp["revenue_opportunity"] > 0
    fc = growth_forecast(db, "Hip-Hop")
    assert len(fc["projection"]) == 4 and len(fc["history"]) == 4
    with pytest.raises(ValueError):
        profitability_score(db, "Polka")
