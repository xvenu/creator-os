"""Phase 3 API: executive, strategy, memory, opportunities, decisions, autonomy, warroom."""
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(tags=["phase3"])


# ---------- Executive / strategy ----------
@router.post("/executive/run", summary="Executive agent pass (analyze→decide→allocate)")
def exec_run(horizon: str = "daily", db: Session = Depends(get_db)):
    from app.modules.executive.engine import ExecutiveAgent
    return ExecutiveAgent.run(db, horizon)


@router.get("/executive/analyze", summary="Business-wide analysis snapshot")
def exec_analyze(db: Session = Depends(get_db)):
    from app.modules.executive.engine import ExecutiveAgent
    return ExecutiveAgent.analyze(db)


class GoalIn(BaseModel):
    title: str
    category: str = "growth"
    target: float = 0.0


@router.post("/executive/goals", summary="Set operational goal")
def goal_set(payload: GoalIn, db: Session = Depends(get_db)):
    from app.modules.executive.engine import set_goal
    return {"id": set_goal(db, **payload.model_dump()).id}


@router.get("/executive/goals", summary="List goals")
def goal_list(db: Session = Depends(get_db)):
    from app.modules.executive.engine import goals
    return {"goals": goals(db)}


@router.get("/strategy/latest", summary="Latest strategic plan")
def strat_latest(horizon: str = "daily", db: Session = Depends(get_db)):
    from app.modules.executive.engine import latest_strategy
    return {"strategy": latest_strategy(db, horizon)}


@router.post("/strategy/generate", summary="Generate strategy (daily|weekly|monthly)")
def strat_gen(horizon: str = "daily", db: Session = Depends(get_db)):
    from app.modules.executive.engine import generate_strategy
    return generate_strategy(db, horizon)


# ---------- Memory ----------
class MemoryIn(BaseModel):
    kind: str
    title: str
    body: str = ""
    score: float = 0.0


@router.post("/memory", summary="Store business memory")
def mem_store(payload: MemoryIn, db: Session = Depends(get_db)):
    from app.modules.memory.engine import store
    return {"id": store(db, **payload.model_dump()).id}


@router.get("/memory", summary="Searchable memory + lessons")
def mem_search(query: str = "", kind: str | None = None, db: Session = Depends(get_db)):
    from app.modules.memory.engine import search, lessons
    return {"results": search(db, query, kind), "lessons": lessons(db)}


# ---------- Opportunities / decisions ----------
@router.post("/opportunities/score", summary="Rank opportunities")
def opp_score(db: Session = Depends(get_db)):
    from app.modules.allocation.engine import score_all
    return {"scored": score_all(db, actor="api")}


@router.get("/opportunities", summary="Priority queues + focus directives")
def opp_queue(db: Session = Depends(get_db)):
    from app.modules.allocation.engine import priority_queue, allocate
    return {"queue": priority_queue(db), "allocation": allocate(db, actor="api")}


class DecideIn(BaseModel):
    question: str
    options: list[dict]


@router.post("/decisions", summary="Evaluate alternatives, select optimal action")
def dec_make(payload: DecideIn, db: Session = Depends(get_db)):
    from app.modules.decision.engine import evaluate
    return evaluate(db, payload.question, payload.options, actor="api")


@router.get("/decisions", summary="Decision audit viewer data")
def dec_list(db: Session = Depends(get_db)):
    from app.modules.decision.engine import decisions
    return {"decisions": decisions(db)}


@router.post("/decisions/{did}/outcome", summary="Track decision outcome")
def dec_outcome(did: int, outcome: str, db: Session = Depends(get_db)):
    from app.modules.decision.engine import record_decision_outcome
    return {"id": record_decision_outcome(db, did, outcome, actor="api").id}


# ---------- Autonomy ----------
@router.post("/autonomy/cycle", summary="Run one autonomous control loop cycle")
def auto_cycle(db: Session = Depends(get_db)):
    from app.modules.autonomy.engine import run_cycle
    return run_cycle(db, actor="api")


@router.get("/autonomy/cycles", summary="Cycle history")
def auto_cycles(db: Session = Depends(get_db)):
    from app.modules.autonomy.engine import cycles
    return {"cycles": cycles(db)}


@router.get("/autonomy/feed", summary="Autonomous activity feed")
def auto_feed(db: Session = Depends(get_db)):
    from app.modules.autonomy.engine import activity_feed
    return {"feed": activity_feed(db)}


@router.post("/autonomy/stop", summary="Emergency stop switch")
def auto_stop(reason: str = "manual", db: Session = Depends(get_db)):
    from app.modules.autonomy.engine import emergency_stop
    return emergency_stop(db, reason, actor="api")


@router.post("/autonomy/override", summary="Executive override (resume|stop)")
def auto_override(action: str = "resume", db: Session = Depends(get_db)):
    from app.modules.autonomy.engine import executive_override
    return executive_override(db, action, actor="api")


@router.get("/autonomy/policy", summary="Policy events")
def auto_policy(db: Session = Depends(get_db)):
    from app.modules.policy.engine import events
    return {"events": events(db)}


# ---------- Warroom / optimizer / director ----------
@router.get("/warroom/briefing", summary="Opportunity + weakness reports")
def war_brief(db: Session = Depends(get_db)):
    from app.modules.warroom.engine import briefing
    return briefing(db)


@router.get("/warroom/attack", summary="Market takeover recommendations")
def war_attack(db: Session = Depends(get_db)):
    from app.modules.warroom.engine import attack_strategies
    return {"strategies": attack_strategies(db)}


@router.post("/revenue-optimizer/run", summary="Revenue optimization pass")
def opt_run(db: Session = Depends(get_db)):
    from app.modules.revenue_optimizer.engine import optimize
    return {"recommendations": optimize(db, actor="api")}


@router.get("/director/directives", summary="Publishing directives + schedules")
def dir_list(db: Session = Depends(get_db)):
    from app.modules.director.engine import build_directives
    return {"directives": build_directives(db, actor="api")}
