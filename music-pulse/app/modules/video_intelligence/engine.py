"""Video Intelligence Engine: learn from rendered/published video performance."""
from __future__ import annotations
from sqlalchemy import func

from app.core.audit import audit


def record_video_metric(db, job_id: int, views: int = 0, watch_time_sec: int = 0,
                        revenue: float = 0.0, ctr: float = 0.0, retention: float = 0.0,
                        audience_growth: int = 0, engagement: int = 0,
                        actor: str = "video_intel"):
    from app.models.phase6 import VideoMetric
    row = VideoMetric(job_id=job_id, views=views, watch_time_sec=watch_time_sec,
                      revenue=revenue, ctr=ctr, retention=retention,
                      audience_growth=audience_growth, engagement=engagement)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "video.measured", "video", row.id, {"job": job_id})
    return row


def _join_package(db):
    from app.models.phase6 import VideoMetric, ContentPackage, ZozaJob
    return (db.query(ContentPackage.type, ContentPackage.target_market,
                     ContentPackage.title,
                     func.sum(VideoMetric.views).label("views"),
                     func.sum(VideoMetric.watch_time_sec).label("watch"),
                     func.sum(VideoMetric.revenue).label("rev"),
                     func.avg(VideoMetric.retention).label("ret"))
            .join(ZozaJob, ZozaJob.package_id == ContentPackage.id)
            .join(VideoMetric, VideoMetric.job_id == ZozaJob.id)
            .group_by(ContentPackage.type, ContentPackage.target_market,
                      ContentPackage.title))


def best_formats(db, limit: int = 5) -> list[dict]:
    rows = _join_package(db).all()
    agg: dict[str, float] = {}
    for ptype, _mkt, _t, views, _w, rev, _r in rows:
        agg[ptype] = agg.get(ptype, 0) + float(views or 0) + float(rev or 0) * 100
    return [{"format": k, "score": round(v, 1)}
            for k, v in sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:limit]]


def best_markets(db, limit: int = 5) -> list[dict]:
    rows = _join_package(db).all()
    agg: dict[str, float] = {}
    for _t, mkt, _ti, views, _w, rev, _r in rows:
        agg[mkt] = agg.get(mkt, 0) + float(views or 0)
    return [{"market": k, "views": round(v, 1)}
            for k, v in sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:limit]]


def feed_back(db, actor: str = "video_intel") -> dict:
    """Push video learnings into Executive/Prediction/Monetization/Learning."""
    from app.modules.memory.engine import store
    formats = best_formats(db, 3)
    markets = best_markets(db, 3)
    note = f"video learnings: formats={formats} markets={markets}"
    store(db, "lesson", "Video performance update", note, actor=actor)
    try:
        from app.core.shared import knowledge
        knowledge.put("video", "best_formats", {"formats": formats},
                      source_pulse="music-pulse")
        knowledge.put("video", "best_markets", {"markets": markets},
                      source_pulse="music-pulse")
    except Exception:
        pass
    audit(db, actor, "video.feedback_applied", "video", "", {})
    return {"formats": formats, "markets": markets}
