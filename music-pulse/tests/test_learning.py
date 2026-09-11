from app.modules.analytics.engine import record_metric
from app.modules.learning.engine import best_genres, best_formats, recommend


def test_learning(db):
    record_metric(db, genre="pop", format="short", topic="hit", views=200, engagement=100)
    record_metric(db, genre="jazz", format="article", topic="deep", views=10, engagement=1)
    assert best_genres(db)[0]["key"] == "pop"
    assert best_formats(db)[0]["key"] == "short"
    recs = recommend(db, 2)
    assert len(recs) >= 1 and recs[0]["genre"] == "pop"
