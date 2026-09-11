from app.modules.analytics.engine import record_metric, totals, top_topics, engagement_rate


def test_analytics_flow(db):
    record_metric(db, topic="afrobeats", genre="afrobeats", format="short",
                  views=100, engagement=25, followers_delta=10)
    record_metric(db, topic="afrobeats", genre="pop", format="article",
                  views=50, engagement=5)
    t = totals(db)
    assert t == {"views": 150, "engagement": 30, "followers_delta": 10}
    assert top_topics(db)[0]["topic"] == "afrobeats"
    assert engagement_rate(db) == round(30 / 150, 4)


def test_engagement_rate_empty(db):
    assert engagement_rate(db) == 0.0
