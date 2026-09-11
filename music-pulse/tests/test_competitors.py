from app.modules.competitors.engine import (
    record_competitor, posting_frequency, content_gaps, weakness_report,
    trend_opportunities,
)


def test_competitor_flow(db):
    record_competitor(db, "Billboard", platform="instagram", post_count=50,
                      engagement_est=100, topics=["charts", "afrobeats"], actor="test")
    record_competitor(db, "Pitchfork", post_count=5, engagement_est=2000,
                      topics=["indie", "reviews"], actor="test")
    freq = posting_frequency(db)
    assert freq[0]["competitor"] == "Billboard"
    gaps = content_gaps(db, our_topics=["charts"])
    assert any(g["topic"] == "afrobeats" for g in gaps)
    weak = weakness_report(db)
    assert any(w["competitor"] == "Billboard" for w in weak)
    opps = trend_opportunities(db)
    assert opps and "action" in opps[0]
