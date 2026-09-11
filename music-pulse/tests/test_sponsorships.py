import pytest
from app.modules.sponsorships.engine import (
    PACKAGES, create_sponsor, create_campaign, record_campaign_revenue,
    sponsor_revenue, campaign_performance,
)


def test_packages():
    assert set(PACKAGES) == {"artist_promotion", "sponsored_ranking",
                             "sponsored_feature", "newsletter", "platform"}


def test_sponsor_campaign_flow(db):
    s = create_sponsor(db, "Acme Records", contact="a@acme.test", actor="test")
    c = create_campaign(db, s.id, "Summer Push", "sponsored_ranking",
                        country="US", genre="Pop", budget=1000.0, actor="test")
    record_campaign_revenue(db, c.id, 2500.0, actor="test")
    rev = sponsor_revenue(db, s.id)
    assert rev == {"sponsor_id": s.id, "campaigns": 1, "revenue": 2500.0,
                   "spend": 1000.0, "roi": 1.5}
    perf = campaign_performance(db)
    assert perf[0]["name"] == "Summer Push" and perf[0]["roi"] == 1.5
    with pytest.raises(ValueError):
        create_campaign(db, s.id, "Bad", "nope")
    with pytest.raises(ValueError):
        create_campaign(db, 99999, "Ghost", "newsletter")
    with pytest.raises(ValueError):
        record_campaign_revenue(db, 99999, 10.0)
