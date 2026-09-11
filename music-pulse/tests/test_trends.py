from app.modules.trends.engine import Trend, fetch_all_trends
from app.core.plugins import registry


def test_fetch_all_uses_registered_providers():
    class Fake:
        name = "fake"
        def fetch(self, limit=5):
            return [Trend(source="fake", title="Song A", artist="X", rank=1, score=9.0)]
    registry.register_trend_provider("fake-test", Fake())
    try:
        trends = fetch_all_trends(5)
        assert any(t.title == "Song A" for t in trends)
        # sorted desc by score
        scores = [t.score for t in trends]
        assert scores == sorted(scores, reverse=True)
    finally:
        del registry.trend_providers["fake-test"]


def test_persist_trends(db):
    from app.modules.trends.engine import persist_trends
    rows = persist_trends(db, [Trend(source="spotify", title="T", artist="A", rank=1, score=5.0)])
    assert len(rows) == 1 and rows[0].id is not None
