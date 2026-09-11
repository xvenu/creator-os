import pytest
from app.modules.content_gateway.engine import (
    build_package, to_schema, from_opportunity, export_json, queue_export, list_packages,
)
from app.modules.video_opportunities.engine import score_topic, rank_topics, top_for_zoza
from app.modules.video_intelligence.engine import (
    record_video_metric, best_formats, best_markets, feed_back,
)
from app.modules.formats.engine import FORMATS, recommend_format, performance_report
from app.modules.feedback.engine import ingest, apply_feedback


def _seed(db):
    from app.modules.market_intelligence.engine import record_country_trend
    from app.modules.profitability.engine import record_genre_analytic
    record_country_trend(db, "US", "Viral Hit", artist="Nova", score=150.0, genre="Pop")
    record_genre_analytic(db, "Pop", "US", views=3000, engagement=600, posts=8)


def test_package_schema(db):
    pkg = build_package(db, "news", "Nova Explodes", summary="Big story",
                        hashtags=["#Pop"], target_market="US", priority_score=88.0,
                        predicted_views=5000.0, predicted_revenue=10.0)
    assert set(pkg) == {"id", "type", "title", "summary", "script", "hashtags",
                        "keywords", "thumbnail_brief", "video_brief", "target_market",
                        "target_platform", "priority_score", "predicted_views",
                        "predicted_revenue", "generated_at",
                        # Phase 7 evidence extension
                        "evidence", "sources", "verification_status",
                        "confidence_score", "rights_status", "attribution"}
    assert export_json(db, pkg["id"])["id"] == pkg["id"]
    assert queue_export(db, pkg["id"])["package_id"] == pkg["id"]
    assert list_packages(db)[0]["id"] == pkg["id"]
    with pytest.raises(ValueError):
        build_package(db, "carrier-pigeon", "x")
    with pytest.raises(ValueError):
        export_json(db, "nope")


def test_opportunity_scoring(db):
    _seed(db)
    s = score_topic(db, "Viral Hit", "US")
    assert s["score"] > 0 and s["predicted_views"] > 0
    ranked = rank_topics(db, ["Viral Hit", "Unknown B-Side"], min_score=1.0)
    assert ranked[0]["topic"] == "Viral Hit"
    assert top_for_zoza(db, limit=3)


def test_video_intelligence(db):
    _seed(db)
    from app.modules.content_gateway.engine import build_package
    from app.modules.zoza.engine import PackageDispatcher, RenderTracker
    pkg = build_package(db, "news", "Nova Story")
    d = PackageDispatcher.dispatch(db, pkg["id"])  # Zoza unreachable in CI → queued
    assert d["state"] in ("queued", "rendering")
    job_id = d["job_id"]
    RenderTracker.record_render(db, job_id, video_url="http://v.test/1.mp4",
                                duration_sec=45)
    record_video_metric(db, job_id, views=10000, watch_time_sec=4000,
                        revenue=20.0, retention=0.45, engagement=800)
    assert best_formats(db)[0]["format"] == "news"
    assert best_markets(db)[0]["market"] == "US"
    fb = feed_back(db)
    assert fb["formats"] and fb["markets"]


def test_formats(db):
    assert len(FORMATS) == 9
    r = recommend_format(db, "Viral Hit")
    assert r["format"] in FORMATS and len(r["ranking"]) == 9 and "rationale" in r


def test_feedback_loop(db):
    _seed(db)
    ingest(db, 1, "views", 5000.0)
    ingest(db, 1, "revenue", 12.5)
    out = apply_feedback(db)
    assert out["events"] == 2 and out["revenue_attributed"] == 12.5
    with pytest.raises(ValueError):
        ingest(db, 1, "telepathy", 1.0)
