"""Zoza connector: push packages to the Zoza Video Factory, track render/publish.

Zoza_anime is file-queue driven: a valid planned Job JSON in its jobs/
dir is picked up by its own worker. We dispatch by invoking Zoza's
`idea_engine.generate_job_from_idea` in-process (imported from ZOZA_DIR,
never copied), falling back to a queued-local state when Zoza is
unreachable. Render/publish trackers poll Zoza's jobs/*.json states:

  QUEUED->queued | PLANNED/AUDIO_READY/ASSETS_* /ASSEMBLING->rendering |
  RENDERED/AWAITING_REVIEW/APPROVED/PUBLISHING->rendered(*) |
  DELIVERED->published | FAILED->failed   (* PUBLISHING counts as rendered
  until DELIVERED; see RenderTracker/PublishTracker split below)
"""
from __future__ import annotations
import json
import os
import sys
import time

from app.core.audit import audit

STATES = ("created", "queued", "rendering", "rendered", "published", "failed")
MAX_ATTEMPTS = 5


def zoza_dir() -> str:
    from app.core.config import get_settings
    s = get_settings()
    explicit = os.environ.get("ZOZA_DIR", "")
    if explicit:
        return explicit
    for cand in (os.path.expanduser("~/Zoza_anime"),
                 os.path.join(os.path.dirname(
                     os.path.dirname(os.path.dirname(
                         os.path.dirname(os.path.abspath(__file__))))), "Zoza_anime")):
        if os.path.isdir(cand):
            return cand
    return ""


class ZozaConnector:
    """Health + reachability of the factory. Never imports Zoza at module load."""

    @staticmethod
    def ping() -> dict:
        zdir = zoza_dir()
        ok = bool(zdir) and os.path.isfile(os.path.join(zdir, "job_queue.py"))
        return {"factory": "zoza-video-factory", "dir": zdir or "not-found",
                "reachable": ok}


class PackageDispatcher:
    @staticmethod
    def dispatch(db, package_id: str, actor: str = "zoza") -> dict:
        """Plan the package inside Zoza (its LLM chain) and register a ZozaJob."""
        from app.models.phase6 import ContentPackage, ZozaJob
        pkg = db.get(ContentPackage, package_id)
        if pkg is None:
            raise ValueError(f"package {package_id} not found")
        job = ZozaJob(package_id=package_id, state="queued", attempts=1)
        db.add(job)
        db.commit()
        db.refresh(job)
        try:
            zoza_job_id = _plan_in_zoza(pkg)
            job.state = "rendering"
            db.commit()
            _emit("PACKAGE_SENT", {"package_id": package_id, "zoza_job": zoza_job_id})
            _emit("VIDEO_REQUESTED", {"package_id": package_id, "zoza_job": zoza_job_id})
            _emit("VIDEO_RENDER_STARTED", {"package_id": package_id})
            audit(db, actor, "zoza.dispatched", "zoza_job", job.id,
                  {"package": package_id, "zoza_job": zoza_job_id})
            return {"job_id": job.id, "state": job.state, "zoza_job": zoza_job_id}
        except Exception as exc:
            job.state = "queued"  # retryable: Zoza unreachable / planning failed
            job.last_error = str(exc)[:500]
            db.commit()
            audit(db, actor, "zoza.dispatch_failed", "zoza_job", job.id,
                  {"error": str(exc)[:200]})
            return {"job_id": job.id, "state": "queued", "error": str(exc)[:200]}

    @staticmethod
    def retry(db, job_id: int, actor: str = "zoza") -> dict:
        from app.models.phase6 import ZozaJob
        job = db.get(ZozaJob, job_id)
        if job is None:
            raise ValueError(f"zoza job {job_id} not found")
        if job.attempts >= MAX_ATTEMPTS:
            job.state = "failed"
            db.commit()
            audit(db, actor, "zoza.failed", "zoza_job", job.id, {})
            return {"job_id": job.id, "state": "failed"}
        return PackageDispatcher.dispatch(db, job.package_id, actor)


def _plan_in_zoza(pkg) -> str:
    """Invoke Zoza's own planner; returns Zoza job_id. Raises when unusable."""
    zdir = zoza_dir()
    if not zdir:
        raise RuntimeError("Zoza factory not found (set ZOZA_DIR)")
    if zdir not in sys.path:
        sys.path.insert(0, zdir)
    os.environ.setdefault("JOBS_DIR", os.path.join(zdir, "jobs"))
    from idea_engine import generate_job_from_idea  # Zoza-owned code
    idea = f"{pkg.title}. {pkg.summary} {pkg.script} {pkg.video_brief}".strip()[:2000]
    path = generate_job_from_idea(idea, output_dir=os.path.join(zdir, "jobs"))
    data = json.load(open(path))
    return data.get("job_id") or os.path.splitext(os.path.basename(path))[0]


def _zoza_job_state(zoza_job_id: str) -> str | None:
    zdir = zoza_dir()
    if not zdir:
        return None
    path = os.path.join(zdir, "jobs", f"{zoza_job_id}.json")
    if not os.path.isfile(path):
        return None
    try:
        return json.load(open(path)).get("state")
    except Exception:
        return None


class RenderTracker:
    _MAP = {"QUEUED": "queued", "PLANNED": "rendering", "AUDIO_READY": "rendering",
            "ASSETS_GENERATING": "rendering", "ASSETS_READY": "rendering",
            "ASSEMBLING": "rendering", "RENDERED": "rendered",
            "AWAITING_REVIEW": "rendered", "APPROVED": "rendered",
            "PUBLISHING": "rendered", "DELIVERED": "published", "FAILED": "failed"}

    @staticmethod
    def poll(db, job_id: int, actor: str = "zoza") -> dict:
        from app.models.phase6 import ZozaJob, RenderResult
        job = db.get(ZozaJob, job_id)
        if job is None:
            raise ValueError(f"zoza job {job_id} not found")
        audit(db, actor, "zoza.render_polled", "zoza_job", job.id, {"state": job.state})
        return {"job_id": job.id, "state": job.state,
                "renders": db.query(RenderResult).filter(
                    RenderResult.job_id == job.id).count()}

    @staticmethod
    def record_render(db, job_id: int, video_url: str = "", duration_sec: int = 0,
                      success: bool = True, actor: str = "zoza"):
        from app.models.phase6 import ZozaJob, RenderResult
        job = db.get(ZozaJob, job_id)
        if job is None:
            raise ValueError(f"zoza job {job_id} not found")
        db.add(RenderResult(job_id=job_id, video_url=video_url,
                            duration_sec=duration_sec, success=success))
        if success and job.state in ("queued", "rendering", "created"):
            job.state = "rendered"
        elif not success:
            job.state = "failed"
        db.commit()
        _emit("VIDEO_RENDERED", {"job_id": job_id, "success": success})
        if success:
            _emit("VIDEO_RENDER_FINISHED", {"job_id": job_id})
        audit(db, actor, "zoza.rendered", "zoza_job", job.id, {"success": success})
        return job


class PublishTracker:
    @staticmethod
    def record_publish(db, job_id: int, platform: str = "", external_id: str = "",
                       success: bool = True, actor: str = "zoza"):
        from app.models.phase6 import ZozaJob, PublishResult
        job = db.get(ZozaJob, job_id)
        if job is None:
            raise ValueError(f"zoza job {job_id} not found")
        db.add(PublishResult(job_id=job_id, platform=platform,
                             external_id=external_id, success=success))
        if success:
            job.state = "published"
        else:
            job.state = "failed"
        db.commit()
        _emit("VIDEO_PUBLISHED", {"job_id": job_id, "platform": platform})
        audit(db, actor, "zoza.published", "zoza_job", job.id, {"platform": platform})
        return job


def _emit(event_type: str, payload: dict) -> None:
    try:
        from app.core.shared import event_bus
        event_bus.publish(event_type, payload, source_pulse="music-pulse")
    except Exception:
        pass


def mark_exported(db, job_id: int, video_path: str, thumbnail_path: str = "",
                  title: str = "", actor: str = "zoza") -> dict:
    """Phase 8: Zoza DELIVERED means *exported*, never published.

    Validates the factory export against shared/contracts.py, stores the
    ExportedAsset for Pulse-owned distribution, emits VIDEO_EXPORTED.
    Zoza-side publish states remain observed-only (see ZOZA_AUDIT.md).
    """
    import json as _json
    from app.models.phase6 import ZozaJob
    from app.models.phase8 import ExportedAsset
    job = db.get(ZozaJob, job_id)
    if job is None:
        raise ValueError(f"zoza job {job_id} not found")
    try:
        from shared.contracts import asset_from_export
    except ImportError:
        from app.core.shared import event_bus as _eb  # noqa: F401
        from shared.contracts import asset_from_export
    pkg_title = ""
    try:
        from app.models.phase6 import ContentPackage
        _pkg = db.get(ContentPackage, job.package_id)
        pkg_title = _pkg.title if _pkg else ""
    except Exception:
        pass
    asset = asset_from_export(
        {"job_id": str(job_id), "status": "rendered", "video_path": video_path,
         "thumbnail_path": thumbnail_path, "metadata": {"title": title or pkg_title}},
        title=title or pkg_title)
    row = ExportedAsset(asset_id=asset["asset_id"], video=asset["video"],
                        thumbnail=asset["thumbnail"], title=asset["title"],
                        description=asset["description"],
                        hashtags_json=_json.dumps(asset["hashtags"]),
                        metadata_json=_json.dumps(asset["metadata"]))
    db.merge(row)
    job.state = "rendered"  # export received; publishing is the Pulse's job
    db.commit()
    _emit("VIDEO_EXPORTED", {"job_id": job_id, "asset_id": asset["asset_id"]})
    audit(db, actor, "zoza.exported", "zoza_job", job.id,
          {"asset": asset["asset_id"]})
    return asset


def dispatch_package(package_id: str) -> dict:
    """RQ worker entrypoint: dispatch with a fresh DB session."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        return PackageDispatcher.dispatch(db, package_id)
    finally:
        db.close()


def render_report(db) -> list[dict]:
    from app.models.phase6 import ZozaJob, RenderResult
    out = []
    for job in db.query(ZozaJob).order_by(ZozaJob.id.desc()).limit(50).all():
        out.append({"job_id": job.id, "package": job.package_id, "state": job.state,
                    "renders": db.query(RenderResult).filter(
                        RenderResult.job_id == job.id).count()})
    return out


def run_pipeline(db, limit: int = 3, actor: str = "pipeline") -> dict:
    """Autonomous video pipeline: top opportunities → packages → Zoza →
    track → measure. No HITL."""
    from app.core.config import get_settings
    from app.modules.video_opportunities.engine import top_for_zoza
    from app.modules.content_gateway.engine import from_opportunity
    if not get_settings().pipeline_enabled:
        return {"status": "disabled"}
    stages: dict[str, str] = {}
    try:
        opps = top_for_zoza(db, limit)
        stages["scored"] = f"{len(opps)} opportunities"
    except Exception as exc:
        return {"status": "failed", "error": f"scoring: {exc}"}
    sent = []
    for opp in opps:
        try:
            pkg = from_opportunity(db, opp["topic"], kind="news", actor=actor)
            res = PackageDispatcher.dispatch(db, pkg["id"], actor)
            sent.append({"package": pkg["id"], **res})
        except Exception as exc:
            sent.append({"topic": opp["topic"], "error": str(exc)[:200]})
    stages["dispatched"] = f"{len([s for s in sent if 'job_id' in s])}/{len(sent)} sent"
    _emit("PACKAGE_SENT", {"count": len(sent)})
    audit(db, actor, "pipeline.ran", "pipeline", "", stages)
    return {"status": "completed", "stages": stages, "items": sent}
