"""Phase 8 API: Creator-OS surface (notifications, telegram, network,
factories, assets) + Pulse-owned distribution. Served here for operability;
extractable to a standalone Creator-OS service without changes."""
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.audit import audit

router = APIRouter(tags=["phase8"])


class NotifyIn(BaseModel):
    event: str
    message: str
    source_pulse: str = "music-pulse"


@router.post("/creator/notifications", summary="Report to notification center")
def creator_notify(payload: NotifyIn, db: Session = Depends(get_db)):
    from app.core.shared import notifications
    from app.models.phase8 import NotificationMirror
    out = notifications.notify(payload.event, payload.message, payload.source_pulse)
    db.add(NotificationMirror(event=payload.event, source_pulse=payload.source_pulse,
                              message=payload.message))
    db.commit()
    audit(db, "api", "notification.reported", "notification", out["id"], {})
    return out


@router.get("/creator/notifications", summary="Recent notifications")
def creator_notifications():
    from app.core.shared import notifications
    return {"notifications": notifications.recent()}


@router.get("/creator/telegram", summary="Creator-OS Telegram agent status")
def creator_telegram():
    from app.core.shared import telegram_agent
    COMMANDS, summaries = telegram_agent.COMMANDS, telegram_agent.summaries
    return {"owner": "creator-os", "commands": list(COMMANDS),
            "pulse_bot": "deprecated", "state": summaries()}


@router.get("/creator/network", summary="Network report + registry")
def creator_network():
    from app.core.shared import network_orchestrator as orch
    orch.heartbeat("music-pulse", "healthy")
    return {**orch.network_report(), "registered": orch.list_registered()}


@router.post("/creator/register", summary="Register pulse or factory")
def creator_register(name: str, role: str = "pulse", db: Session = Depends(get_db)):
    from app.core.shared import network_orchestrator as orch
    from app.models.phase8 import PulseRegistration
    out = (orch.register_factory(name) if role == "factory"
           else orch.register_pulse(name))
    db.add(PulseRegistration(name=name, role=role))
    db.commit()
    audit(db, "api", "creator.registered", "registration", "", {"name": name})
    return out


@router.get("/creator/factories", summary="Registered factories + routing")
def creator_factories():
    from app.core.shared import network_orchestrator as orch
    return {"factories": orch.list_registered("factory"),
            "route_preview": orch.route_to_factory([{"demo": 1}])}


@router.get("/creator/assets", summary="Exported assets (contract-validated)")
def creator_assets(db: Session = Depends(get_db)):
    from app.models.phase8 import ExportedAsset
    rows = db.query(ExportedAsset).order_by(ExportedAsset.created_at.desc()).limit(50).all()
    return {"assets": [{"asset_id": r.asset_id, "title": r.title,
                        "published": r.published} for r in rows]}


@router.post("/distribution/publish/{asset_id}", summary="Pulse publishes an export")
def dist_publish(asset_id: str, platform: str = "log", db: Session = Depends(get_db)):
    from app.modules.distribution.engine import publish_asset
    return publish_asset(db, asset_id, platform, actor="api")


@router.post("/distribution/track/{asset_id}", summary="Track published asset")
def dist_track(asset_id: str, views: int = 0, engagement: int = 0,
               revenue: float = 0.0, db: Session = Depends(get_db)):
    from app.modules.distribution.engine import track_performance
    return track_performance(db, asset_id, views, engagement, revenue=revenue,
                             actor="api")


@router.post("/zoza/export/{jid}", summary="Accept Zoza export (render-only)")
def zoza_export(jid: int, video_path: str, thumbnail_path: str = "",
                db: Session = Depends(get_db)):
    from app.modules.zoza.engine import mark_exported
    return mark_exported(db, jid, video_path, thumbnail_path, actor="api")
