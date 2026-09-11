"""FastAPI routers for all modules."""
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.audit import audit

router = APIRouter()


class TrendRefresh(BaseModel):
    limit_per_source: int = 10


@router.get("/trends")
def list_trends(db: Session = Depends(get_db)):
    from app.models.models import TrendItem
    rows = db.query(TrendItem).order_by(TrendItem.score.desc()).limit(100).all()
    return [{"id": r.id, "source": r.source, "title": r.title, "artist": r.artist,
             "rank": r.rank, "score": r.score, "url": r.url} for r in rows]


@router.post("/trends/refresh")
def refresh_trends(payload: TrendRefresh, db: Session = Depends(get_db)):
    from app.modules.trends.engine import fetch_all_trends, persist_trends
    trends = fetch_all_trends(payload.limit_per_source)
    persist_trends(db, trends)
    audit(db, "api", "trends.refresh", "trend", "", {"count": len(trends)})
    return {"fetched": len(trends)}


class GenRequest(BaseModel):
    kind: str
    topic: str
    genre: str = ""
    artist: str = ""


@router.post("/content/generate")
def api_generate(req: GenRequest, db: Session = Depends(get_db)):
    from app.modules.content.engine import generate_content, persist_content
    c = generate_content(req.kind, req.topic, req.genre, req.artist)
    row = persist_content(db, c)
    audit(db, "api", "content.generate", "content", row.id, {"kind": req.kind})
    return {"id": row.id, "title": row.title, "body": row.body}


@router.get("/content")
def list_content(db: Session = Depends(get_db)):
    from app.models.models import ContentItem
    rows = db.query(ContentItem).order_by(ContentItem.id.desc()).limit(100).all()
    return [{"id": r.id, "kind": r.kind, "title": r.title, "status": r.status} for r in rows]


class QueueRequest(BaseModel):
    content_id: int
    platform: str = "log"
    delay_minutes: int = 0


@router.post("/publish/queue")
def api_queue(req: QueueRequest, db: Session = Depends(get_db)):
    from app.modules.publisher.engine import queue_post
    job = queue_post(db, req.content_id, req.platform, req.delay_minutes, actor="api")
    return {"job_id": job.id, "status": job.status}


@router.post("/publish/run")
def api_run(db: Session = Depends(get_db)):
    from app.modules.publisher.engine import publish_due_jobs
    return publish_due_jobs(db)


class MetricRequest(BaseModel):
    content_id: int = 0
    platform: str = ""
    views: int = 0
    engagement: int = 0
    followers_delta: int = 0
    topic: str = ""
    genre: str = ""
    format: str = ""


@router.post("/analytics/metric")
def api_metric(req: MetricRequest, db: Session = Depends(get_db)):
    from app.modules.analytics.engine import record_metric
    row = record_metric(db, **req.model_dump())
    return {"id": row.id}


@router.get("/analytics/summary")
def api_summary(db: Session = Depends(get_db)):
    from app.modules.analytics.engine import totals, top_topics, engagement_rate
    return {"totals": totals(db), "top_topics": top_topics(db),
            "engagement_rate": engagement_rate(db)}


@router.get("/learning/recommend")
def api_recommend(db: Session = Depends(get_db)):
    from app.modules.learning.engine import best_genres, best_formats, recommend
    return {"genres": best_genres(db), "formats": best_formats(db),
            "recommendations": recommend(db)}


@router.get("/audit")
def api_audit(db: Session = Depends(get_db)):
    from app.models.models import AuditLog
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(100).all()
    return [{"id": r.id, "actor": r.actor, "action": r.action,
             "entity": f"{r.entity_type}:{r.entity_id}", "at": str(r.created_at)} for r in rows]
