"""Phase 4 tests: research + planner services and agents."""
from __future__ import annotations

from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentStatus
from app.db.models.phase4 import ContentPlan, ResearchBrief
from app.services import planner_service as planner
from app.services import research_service as svc


def test_aggregate_facts_dedupes_keeps_confident(sample_intel_items):
    facts = svc.aggregate_facts(sample_intel_items)
    texts = [f["text"] for f in facts]
    assert texts.count("Arsenal confirmed a record signing.") == 1
    dup = next(f for f in facts if f["text"] == "Arsenal confirmed a record signing.")
    assert dup["confidence"] == 0.9


def test_enrich_entities_ranks_by_mentions(sample_intel_items):
    entities = svc.enrich_entities(sample_intel_items)
    assert entities["clubs"][0] == "arsenal"
    assert "premier league" in entities["competitions"]


def test_build_timeline_orders_chronologically(sample_intel_items):
    timeline = svc.build_timeline(sample_intel_items)
    assert timeline[0]["at"] <= timeline[1]["at"]


def test_build_brief_output_shape(sample_intel_items):
    brief = svc.build_brief("Arsenal record signing", sample_intel_items)
    for key in ("topic", "facts", "entities", "timeline", "supporting_points",
                "confidence", "references"):
        assert key in brief, f"missing {key}"
    assert 0.0 <= brief["confidence"] <= 1.0
    assert brief["facts"]


def test_plan_item_priority_and_platforms():
    entry = planner.plan_item({"topic": "Derby", "urgency": "critical",
                               "content_type": "match_preview", "estimated_reach": 5000,
                               "target_platforms": ["youtube"]})
    assert entry["publish_priority"] == "critical"
    assert entry["content_id"].startswith("ct-")
    assert entry["publish_window"]["hours"]


def test_build_calendar_orders_by_urgency():
    opps = [
        {"topic": "low item", "urgency": "low", "score": 0.9, "content_type": "short"},
        {"topic": "hot item", "urgency": "critical", "score": 0.5, "content_type": "short"},
    ]
    cal = planner.build_calendar(opps)
    assert cal[0]["topic"] == "hot item"
    assert cal[0]["queue_position"] == 1


def test_next_publish_slot_format():
    import datetime as dt
    slot = planner.next_publish_slot("high", dt.datetime(2026, 9, 7, 10, 0, tzinfo=dt.timezone.utc))
    assert slot.startswith("2026-09-07")


async def test_research_agent_persists(session_factory, sample_intel_items):
    from app.agents.research_agent import ResearchAgent

    result = await ResearchAgent().run(
        AgentContext(payload={"topic": "Arsenal record signing", "items": sample_intel_items}))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["researched"] == 1
    assert result.output["items"][0]["brief_id"]
    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(ResearchBrief))).scalar() == 1


async def test_planner_agent_persists_and_emits_task(session_factory, sample_opportunity_items):
    from app.agents.planner_agent import ContentPlannerAgent

    opps = [{"topic": "Derby", "title": "Derby", "urgency": "high", "score": 0.8,
             "content_type": "match_preview", "estimated_reach": 9000,
             "target_platforms": ["youtube", "tiktok"]}]
    result = await ContentPlannerAgent().run(AgentContext(payload={
        "opportunities": opps,
        "emit_task": {"agent": "script_writer", "kind": "create_script"}}))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["planned"] == 1
    assert result.output["items"][0]["next_task_id"] is not None
    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(ContentPlan))).scalar() == 1


def test_expand_topic_suggests_club_angles(sample_intel_items):
    entities = svc.enrich_entities(sample_intel_items)
    expanded = svc.expand_topic("Arsenal record signing", entities)
    assert expanded[0] == "Arsenal record signing"
    assert any("arsenal" in e.lower() for e in expanded[1:])


def test_narrative_confidence_grows_with_evidence(sample_intel_items):
    entities = svc.enrich_entities(sample_intel_items)
    _, full_conf = svc.extract_narrative(sample_intel_items, entities)
    _, thin_conf = svc.extract_narrative(sample_intel_items[:1], entities)
    assert full_conf >= thin_conf


def test_plan_item_defaults_unknown_urgency():
    entry = planner.plan_item({"topic": "T", "urgency": "whenever", "content_type": "short"})
    assert entry["publish_priority"] == "medium"


def test_content_id_deterministic():
    assert planner.make_content_id("Derby", "short") == planner.make_content_id("Derby", "short")
    assert planner.make_content_id("Derby", "short") != planner.make_content_id("Derby", "long_form")
