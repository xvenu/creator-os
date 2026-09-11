"""Phase 6 API: packages, zoza, videos, events, feedback, network, knowledge."""
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(tags=["phase6"])


# ---------- Packages ----------
class PackageIn(BaseModel):
    type: str
    title: str
    summary: str = ""
    script: str = ""
    target_market: str = "US"
    target_platform: str = "youtube"


@router.post("/packages", summary="Create content package")
def pkg_create(payload: PackageIn, db: Session = Depends(get_db)):
    from app.modules.content_gateway.engine import build_package
    return build_package(db, actor="api", **payload.model_dump())


@router.post("/packages/from-opportunity", summary="Package from live intelligence")
def pkg_from_opp(topic: str, kind: str = "news", market: str = "US",
                 db: Session = Depends(get_db)):
    from app.modules.content_gateway.engine import from_opportunity
    return from_opportunity(db, topic, kind, market, actor="api")


@router.get("/packages", summary="Content package queue")
def pkg_list(db: Session = Depends(get_db)):
    from app.modules.content_gateway.engine import list_packages
    return {"packages": list_packages(db)}


@router.get("/packages/{pid}/export", summary="JSON export of a package")
def pkg_export(pid: str, db: Session = Depends(get_db)):
    from app.modules.content_gateway.engine import export_json
    return export_json(db, pid, actor="api")


@router.post("/packages/{pid}/queue", summary="Queue package for Zoza dispatch")
def pkg_queue(pid: str, db: Session = Depends(get_db)):
    from app.modules.content_gateway.engine import queue_export
    return queue_export(db, pid, actor="api")


@router.get("/packages/opportunities/top", summary="Top video opportunities")
def opp_top(limit: int = 5, market: str = "US", db: Session = Depends(get_db)):
    from app.modules.video_opportunities.engine import top_for_zoza
    return {"opportunities": top_for_zoza(db, limit, market)}


@router.get("/packages/formats/recommend", summary="Optimal format decision")
def fmt_rec(topic: str, market: str = "US", db: Session = Depends(get_db)):
    from app.modules.formats.engine import recommend_format, performance_report
    return {"recommendation": recommend_format(db, topic, market),
            "performance": performance_report(db)}


# ---------- Zoza / videos ----------
@router.get("/zoza/ping", summary="Zoza Video Factory reachability")
def zoza_ping():
    from app.modules.zoza.engine import ZozaConnector
    return ZozaConnector.ping()


@router.post("/zoza/dispatch/{pid}", summary="Dispatch package to Zoza")
def zoza_dispatch(pid: str, db: Session = Depends(get_db)):
    from app.modules.zoza.engine import PackageDispatcher
    return PackageDispatcher.dispatch(db, pid, actor="api")


@router.post("/zoza/retry/{jid}", summary="Retry failed Zoza job")
def zoza_retry(jid: int, db: Session = Depends(get_db)):
    from app.modules.zoza.engine import PackageDispatcher
    return PackageDispatcher.retry(db, jid, actor="api")


@router.get("/zoza/jobs", summary="Render + publishing reports")
def zoza_jobs(db: Session = Depends(get_db)):
    from app.modules.zoza.engine import render_report
    return {"jobs": render_report(db)}


@router.post("/zoza/render/{jid}", summary="Record render result (Zoza callback)")
def zoza_render(jid: int, video_url: str = "", duration_sec: int = 0,
                db: Session = Depends(get_db)):
    from app.modules.zoza.engine import RenderTracker
    job = RenderTracker.record_render(db, jid, video_url, duration_sec, actor="api")
    return {"job_id": job.id, "state": job.state}


@router.post("/zoza/publish/{jid}", summary="Record publish result (Zoza callback)")
def zoza_publish(jid: int, platform: str = "", external_id: str = "",
                 db: Session = Depends(get_db)):
    from app.modules.zoza.engine import PublishTracker
    job = PublishTracker.record_publish(db, jid, platform, external_id, actor="api")
    return {"job_id": job.id, "state": job.state}


@router.post("/pipeline/run", summary="Autonomous video pipeline run")
def pipe_run(limit: int = 3, db: Session = Depends(get_db)):
    from app.modules.zoza.engine import run_pipeline
    return run_pipeline(db, limit, actor="api")


class VideoMetricIn(BaseModel):
    job_id: int
    views: int = 0
    watch_time_sec: int = 0
    revenue: float = 0.0
    ctr: float = 0.0
    retention: float = 0.0
    audience_growth: int = 0
    engagement: int = 0


@router.post("/videos/metrics", summary="Ingest video performance")
def vid_metric(payload: VideoMetricIn, db: Session = Depends(get_db)):
    from app.modules.video_intelligence.engine import record_video_metric
    return {"id": record_video_metric(db, **payload.model_dump(), actor="api").id}


@router.get("/videos/intelligence", summary="Video intelligence: best formats/markets")
def vid_intel(db: Session = Depends(get_db)):
    from app.modules.video_intelligence.engine import best_formats, best_markets, feed_back
    return {"formats": best_formats(db), "markets": best_markets(db),
            "applied": feed_back(db, actor="api")}


# ---------- Events / knowledge / network ----------
@router.post("/events", summary="Publish Creator-OS event")
def evt_pub(event_type: str, source_pulse: str = "music-pulse", db: Session = Depends(get_db)):
    from app.core.shared import event_bus
    from app.core.audit import audit
    out = event_bus.publish(event_type, {}, source_pulse=source_pulse)
    audit(db, "api", "event.published", "event", out["id"], {"type": event_type})
    return out


@router.get("/events", summary="Event bus monitor (persisted, replayable)")
def evt_list(limit: int = 50):
    from app.core.shared import event_bus
    return {"events": event_bus.history(limit)}


@router.get("/events/replay", summary="Replay events since id")
def evt_replay(since_id: int = 0):
    from app.core.shared import event_bus
    return {"events": event_bus.replay(since_id)}


@router.post("/knowledge", summary="Write shared knowledge")
def kn_put(domain: str, key: str, value: dict, db: Session = Depends(get_db)):
    from app.core.shared import knowledge
    from app.models.phase6 import SharedKnowledge
    import json as _json
    out = knowledge.put(domain, key, value, source_pulse="music-pulse")
    db.add(SharedKnowledge(domain=domain, key=key, value_json=_json.dumps(value)))
    db.commit()
    return out


@router.get("/knowledge", summary="Shared knowledge center")
def kn_search(domain: str, query: str = ""):
    from app.core.shared import knowledge
    return {"results": knowledge.search(domain, query)}


@router.get("/network/health", summary="Creator network health + reports")
def net_health(db: Session = Depends(get_db)):
    from app.core.shared import network_orchestrator as orch
    orch.heartbeat("music-pulse", "healthy")
    return orch.network_report()


class FeedbackIn(BaseModel):
    job_id: int
    kind: str
    value: float = 0.0


@router.post("/feedback", summary="Receive video feedback metric")
def fb_in(payload: FeedbackIn, db: Session = Depends(get_db)):
    from app.modules.feedback.engine import ingest
    return {"id": ingest(db, actor="api", **payload.model_dump()).id}


@router.post("/feedback/apply", summary="Apply feedback to brain (autonomous)")
def fb_apply(db: Session = Depends(get_db)):
    from app.modules.feedback.engine import apply_feedback
    return apply_feedback(db, actor="api")
