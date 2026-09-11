"""Autonomous Control Loop: Observe→…→Learn→Repeat.

Continuous, fault-tolerant, auto-recovering, fully audited.
Safety: emergency_stop() halts cycles; executive_override() resumes or
forces a decision. No manual approvals are ever required to operate.
"""
from __future__ import annotations
import json
import traceback

from app.core.audit import audit

STAGES = ("observe", "analyze", "predict", "decide", "plan",
          "create", "publish", "measure", "learn")

_STOPPED = {"active": False, "reason": ""}  # process-local kill switch (mirrored to DB)


def is_running() -> bool:
    from app.core.config import get_settings
    return bool(get_settings().autonomy_enabled) and not _STOPPED["active"]


def emergency_stop(db, reason: str = "manual", actor: str = "admin") -> dict:
    from app.models.phase3 import AutonomyCycle
    _STOPPED.update(active=True, reason=reason)
    row = AutonomyCycle(status="stopped", stages_json=json.dumps({"reason": reason}))
    db.add(row)
    db.commit()
    audit(db, actor, "autonomy.emergency_stop", "autonomy", row.id, {"reason": reason})
    return {"stopped": True, "reason": reason}


def executive_override(db, action: str = "resume", actor: str = "admin") -> dict:
    """resume → clear stop; stop → halt; force_decide handled by decision engine."""
    from app.models.phase3 import AutonomyCycle
    if action == "resume":
        _STOPPED.update(active=False, reason="")
    elif action == "stop":
        return emergency_stop(db, "executive override", actor)
    else:
        raise ValueError("action must be resume|stop")
    row = AutonomyCycle(status="completed",
                        stages_json=json.dumps({"override": action}))
    db.add(row)
    db.commit()
    audit(db, actor, "autonomy.override", "autonomy", row.id, {"action": action})
    return {"running": is_running()}


def run_cycle(db, actor: str = "autonomy") -> dict:
    """Execute one full loop. Each stage is isolated: failures are captured,
    the cycle auto-recovers (continues to measure/learn) and is recorded."""
    from app.models.phase3 import AutonomyCycle
    from app.modules.memory.engine import store
    if not is_running():
        return {"status": "skipped", "reason": _STOPPED["reason"] or "disabled"}
    stage_status: dict[str, str] = {}
    ctx: dict = {}

    def stage(name: str, fn):
        try:
            ctx[name] = fn()
            stage_status[name] = "ok"
        except Exception as exc:  # fault tolerance: capture + continue
            stage_status[name] = f"failed: {exc}"
            audit(db, actor, "autonomy.stage_failed", "autonomy", "",
                  {"stage": name, "error": str(exc)[:500]})

    from app.modules.executive.engine import ExecutiveAgent
    from app.modules.allocation.engine import score_all, allocate
    from app.modules.decision.engine import decide_focus
    from app.modules.director.engine import build_directives, execute_directives
    from app.modules.publisher.engine import publish_due_jobs
    from app.modules.analytics.engine import totals
    from app.modules.revenue_optimizer.engine import optimize

    stage("observe", lambda: ExecutiveAgent.analyze(db))
    stage("analyze", lambda: {"opportunities": score_all(db, actor)})
    stage("predict", lambda: optimize(db, actor))
    stage("decide", lambda: decide_focus(db, actor))
    stage("plan", lambda: ExecutiveAgent.run(db, actor=actor))
    stage("create", lambda: execute_directives(db, build_directives(db, actor=actor), actor))
    stage("publish", lambda: publish_due_jobs(db))
    stage("measure", lambda: totals(db))
    learned = stage("learn", lambda: store(
        db, "lesson", f"cycle outcome {len([s for s in stage_status.values() if s == 'ok'])}/{len(STAGES)} stages ok",
        json.dumps(stage_status), actor=actor))
    del learned  # stored for audit; ctx holds the rest

    failed = [k for k, v in stage_status.items() if v != "ok"]
    status = "completed" if not failed else "failed"
    row = AutonomyCycle(status=status, stages_json=json.dumps(stage_status),
                        error="" if not failed else "; ".join(failed))
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, f"autonomy.cycle_{status}", "autonomy", row.id, stage_status)
    _ = allocate  # (allocated inside ExecutiveAgent.run; kept import explicit)
    return {"cycle_id": row.id, "status": status, "stages": stage_status, "ctx_keys": list(ctx)}


def cycles(db, limit: int = 20) -> list[dict]:
    from app.models.phase3 import AutonomyCycle
    rows = db.query(AutonomyCycle).order_by(
        AutonomyCycle.id.desc()).limit(limit).all()
    return [{"id": r.id, "status": r.status,
             "stages": json.loads(r.stages_json or "{}"),
             "at": str(r.created_at)} for r in rows]


def activity_feed(db, limit: int = 30) -> list[dict]:
    """Autonomous activity feed = recent audit trail for machine actors."""
    from app.models.models import AuditLog
    rows = (db.query(AuditLog).filter(AuditLog.actor.in_(
        ["autonomy", "executive", "director", "allocator", "optimizer", "warroom", "policy"]))
        .order_by(AuditLog.id.desc()).limit(limit).all())
    return [{"actor": r.actor, "action": r.action,
             "entity": f"{r.entity_type}:{r.entity_id}", "at": str(r.created_at)}
            for r in rows]


V4_STAGES = ("observe", "analyze", "predict", "discover", "allocate", "create",
             "publish", "acquire", "monetize", "measure", "learn")


def run_cycle_v4(db, actor: str = "autonomy") -> dict:
    """Phase 4 extended loop: Observe→Analyze→Predict→Discover→Allocate→
    Create→Publish→Acquire→Monetize→Measure→Learn. Fault-tolerant + audited;
    phase-3 run_cycle() is untouched."""
    import json as _json
    from app.models.phase3 import AutonomyCycle
    from app.modules.memory.engine import store
    if not is_running():
        return {"status": "skipped", "reason": _STOPPED["reason"] or "disabled"}
    stage_status: dict[str, str] = {}

    def stage(name: str, fn):
        try:
            fn()
            stage_status[name] = "ok"
        except Exception as exc:
            stage_status[name] = f"failed: {exc}"
            audit(db, actor, "autonomy_v4.stage_failed", "autonomy", "",
                  {"stage": name, "error": str(exc)[:500]})

    from app.modules.executive.engine import ExecutiveAgent
    from app.modules.allocation.engine import score_all
    from app.modules.prediction.engine import forecast_report
    from app.modules.breakout.engine import scan
    from app.modules.director.engine import build_directives, execute_directives
    from app.modules.publisher.engine import publish_due_jobs
    from app.modules.acquisition.engine import growth_report
    from app.modules.monetization.engine import InventoryManager
    from app.modules.revenue_execution.engine import plan_actions
    from app.modules.analytics.engine import totals

    stage("observe", lambda: ExecutiveAgent.analyze(db))
    stage("analyze", lambda: score_all(db, actor))
    stage("predict", lambda: forecast_report(db))
    stage("discover", lambda: scan(db, actor))
    stage("allocate", lambda: ExecutiveAgent.run(db, actor=actor))
    stage("create", lambda: execute_directives(db, build_directives(db, actor=actor), actor))
    stage("publish", lambda: publish_due_jobs(db))
    stage("acquire", lambda: growth_report(db))
    stage("monetize", lambda: (plan_actions(db, actor), InventoryManager.utilization(db)))
    stage("measure", lambda: totals(db))
    stage("learn", lambda: store(db, "lesson", "v4 cycle outcome",
                                 _json.dumps(stage_status), actor=actor))

    failed = [k for k, v in stage_status.items() if v != "ok"]
    status = "completed" if not failed else "failed"
    row = AutonomyCycle(status=status, stages_json=_json.dumps(
        {"loop": "v4", **stage_status}), error="; ".join(failed))
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, f"autonomy_v4.cycle_{status}", "autonomy", row.id, stage_status)
    return {"cycle_id": row.id, "status": status, "stages": stage_status}
