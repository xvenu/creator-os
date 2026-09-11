"""Phase 3 tests: executive decision engine + Executive Agent (tasks, logs, memory)."""
from __future__ import annotations

from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentStatus
from app.db.models import Memory, Task
from app.db.models.phase3 import DecisionLog, ExecutiveDecision
from app.services import executive_service as svc


def _signals(**over) -> dict:
    base = {"news_importance": 0.5, "transfer_credibility": 0.5,
            "prediction_confidence": 0.5, "campaign_roi": 0.5, "trend_score": 0.5}
    return {**base, **over}


def test_opportunity_score_weighted():
    ev = svc.evaluate_opportunity(_signals(news_importance=1.0))
    # 1.0*.25 + .5*(.2+.2+.15+.2) = .25 + .375 = .625
    assert ev["opportunity_score"] == 0.625
    assert ev["tier"] == "create" and ev["priority_level"] == "high"


def test_tier_boundaries():
    assert svc.evaluate_opportunity(_signals(
        news_importance=1, transfer_credibility=1, prediction_confidence=1,
        campaign_roi=1, trend_score=1))["tier"] == "immediate"
    assert svc.evaluate_opportunity(_signals(
        news_importance=0, transfer_credibility=0, prediction_confidence=0,
        campaign_roi=0, trend_score=0))["tier"] == "ignore"
    assert svc.evaluate_opportunity(_signals())["tier"] == "monitor"  # all .5 → .5


def test_prioritize_orders_by_tier_then_score():
    items = [
        {"title": "b", "tier": "create", "opportunity_score": 0.9, "urgency": "high"},
        {"title": "a", "tier": "immediate", "opportunity_score": 0.81, "urgency": "critical"},
        {"title": "c", "tier": "ignore", "opportunity_score": 0.1, "urgency": "low"},
    ]
    ranked = svc.prioritize_opportunities(items)
    assert [i["title"] for i in ranked] == ["a", "b", "c"]


def test_recommendation_answers_five_questions(sample_decision_candidate):
    decision = svc.decide(sample_decision_candidate)
    rec = decision["recommendation"]
    assert rec["should_create_content"] is True
    assert rec["is_trending"] is True
    assert rec["is_urgent"] is False  # 0.755 → create, not immediate
    assert "youtube" in rec["target_platforms"]
    assert rec["content_type"] == "match_preview"
    assert decision["expected_reach"] > 0 and decision["expected_engagement"] > 0


def test_reach_and_engagement_scale():
    big = svc.estimate_reach(0.9, 0.9, ["youtube", "tiktok", "instagram"])
    small = svc.estimate_reach(0.2, 0.1, ["x"])
    assert big > small > 0
    assert svc.estimate_engagement(0.9, 0.9) > svc.estimate_engagement(0.2, 0.1)


async def test_executive_agent_decides_generates_task_and_logs(
    session_factory, sample_decision_candidate
):
    from app.agents.executive_agent import ExecutiveAgent

    agent = ExecutiveAgent()
    result = await agent.run(AgentContext(payload=sample_decision_candidate))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["decided"] == 1
    item = result.output["items"][0]
    assert item["recommendation"]["should_create_content"] is True
    assert len(item["task_ids"]) == 1  # create tier → single create_script task

    async with session_factory() as session:
        decisions = (await session.execute(select(ExecutiveDecision))).scalars().all()
        assert len(decisions) == 1
        tasks = (await session.execute(select(Task))).scalars().all()
        assert len(tasks) == 1
        assert tasks[0].kind == "create_script"
        assert tasks[0].agent_name == "script_writer"
        assert tasks[0].payload["source"] == "executive_decision"
        logs = (await session.execute(select(DecisionLog))).scalars().all()
        events = {l.event for l in logs}
        assert {"decided", "task_generated"} <= events
        mem = (await session.execute(
            select(Memory).where(Memory.kind == "successful_executive_decisions")
        )).scalars().all()
        assert len(mem) == 1


async def test_immediate_tier_generates_two_tasks(session_factory):
    from app.agents.executive_agent import ExecutiveAgent

    hot = {"title": "BREAKING: Title Race Decided", "topic": "title race",
           "source_kind": "news",
           "signals": {"news_importance": 1.0, "transfer_credibility": 0.9,
                       "prediction_confidence": 0.9, "campaign_roi": 0.9, "trend_score": 1.0}}
    result = await ExecutiveAgent().run(AgentContext(payload=hot))
    assert result.output["items"][0]["urgency"] == "critical"
    assert result.output["tasks_created"] == 2
    assert len(result.output["items"][0]["task_ids"]) == 2


async def test_ignore_tier_generates_no_tasks(session_factory):
    from app.agents.executive_agent import ExecutiveAgent

    cold = {"title": "Grassroots Roundup", "topic": "grassroots", "source_kind": "news",
            "signals": {"news_importance": 0.1, "transfer_credibility": 0.0,
                        "prediction_confidence": 0.1, "campaign_roi": 0.1, "trend_score": 0.1}}
    result = await ExecutiveAgent().run(AgentContext(payload=cold))
    assert result.output["tasks_created"] == 0
    assert result.output["items"][0]["task_ids"] == []


def test_monitor_tier_recommends_watchful_waiting():
    decision = svc.decide({"title": "Mild Interest", "topic": "mid-table clash",
                           "source_kind": "news", "signals": _signals()})
    assert decision["tier"] == "monitor"
    rec = decision["recommendation"]
    assert rec["should_create_content"] is False
    assert rec["action"] == "keep monitoring"
    assert rec["target_platforms"] == ["tiktok"]


def test_transfer_source_maps_to_transfer_update():
    rec = svc.generate_recommendation({"opportunity_score": 0.85, "tier": "immediate",
                                       "trend_score": 0.9, "source_kind": "transfer"})
    assert rec["content_type"] == "transfer_update"
    assert rec["is_urgent"] is True
