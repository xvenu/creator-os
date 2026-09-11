import pytest
from app.modules.market_intelligence.engine import (
    record_country_trend, country_rankings, velocity, fastest_growing,
    cross_country_compare, trend_migration,
)


def test_record_and_rankings(db):
    record_country_trend(db, "US", "Hit Song", artist="Star A", score=90.0, rank=1)
    record_country_trend(db, "US", "Hit Song", artist="Star A", score=95.0, rank=1)
    record_country_trend(db, "UK", "Other Song", artist="Star B", score=50.0, rank=3)
    rows = country_rankings(db, "US")
    assert rows[0]["title"] == "Hit Song" and rows[0]["score"] == 95.0
    assert all(r["title"] != "Other Song" for r in rows)  # independent per country


def test_invalid_country(db):
    with pytest.raises(ValueError):
        record_country_trend(db, "XX", "X")


def test_velocity_and_fastest(db):
    record_country_trend(db, "US", "Grower", artist="Riser", score=100.0, genre="Pop")
    assert velocity(db, "US", title="Grower") >= 0
    fast = fastest_growing(db, "artist", country="US")
    assert fast[0]["key"] == "Riser"
    assert fastest_growing(db, "genre")[0]["key"] == "Pop"
    with pytest.raises(ValueError):
        fastest_growing(db, "nonsense")


def test_compare_and_migration(db):
    record_country_trend(db, "US", "Global Hit", artist="Star", score=80.0)
    record_country_trend(db, "UK", "Global Hit", artist="Star", score=70.0)
    comp = cross_country_compare(db, title="Global Hit")
    assert {c["country"] for c in comp} == {"US", "UK"}
    mig = trend_migration(db)
    assert any(m["title"] == "Global Hit" and m["countries"] == 2 for m in mig)
