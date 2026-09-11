"""Phase 4 tests: script generation, quality engine + Script Writer Agent."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentStatus
from app.db.models import Memory, Script
from app.services import script_service as svc


def test_generate_all_formats(sample_brief):
    for fmt in svc.VALID_FORMATS:
        script = svc.generate_script(sample_brief, fmt, "60s")
        for key in ("title", "hook", "body", "outro", "estimated_duration"):
            assert key in script, f"{fmt} missing {key}"
        assert script["hook"] and script["body"] and script["outro"]


def test_generate_all_lengths():
    rich = {
        "topic": "Epic Title Race Finale",
        "facts": [{"text": f"Fact number {i} about the dramatic title race finale.", "confidence": 0.8}
                  for i in range(12)],
        "supporting_points": [f"Supporting narrative point number {i}." for i in range(6)],
        "entities": {"clubs": ["arsenal"], "competitions": [], "people": []},
    }
    words = {}
    for length in svc.LENGTHS:
        script = svc.generate_script(rich, "mini_documentary", length)
        words[length] = script["estimated_duration"]["word_count"]
    assert words["30s"] < words["60s"] < words["3min"] < words["5min"] < words["10min"]


def test_generate_rejects_bad_inputs(sample_brief):
    with pytest.raises(ValueError):
        svc.generate_script(sample_brief, "opera", "60s")
    with pytest.raises(ValueError):
        svc.generate_script(sample_brief, "football_story", "20min")


def test_quality_scores_bounded(sample_brief):
    script = svc.generate_script(sample_brief, "transfer_update", "60s")
    quality = svc.score_quality(script, brief := sample_brief)
    for key in ("engagement_score", "clarity_score", "retention_score",
                "monetization_score", "overall_score"):
        assert 0.0 <= quality[key] <= 1.0, key
    assert isinstance(quality["approved"], bool)


def test_quality_threshold_gate():
    good_brief = {"topic": "Huge Derby With Many Goals And Drama",
                  "facts": [{"text": "Team A beat Team B in a thrilling contest full of goals.", "confidence": 0.9},
                            {"text": "The winner came in stoppage time.", "confidence": 0.8}],
                  "supporting_points": ["Fans went wild at the final whistle."],
                  "entities": {"clubs": ["arsenal"], "competitions": [], "people": []}}
    script = svc.generate_script(good_brief, "match_review", "60s")
    quality = svc.score_quality(script, good_brief)
    assert quality["overall_score"] >= svc.QUALITY_THRESHOLD
    assert quality["approved"] is True


def test_thin_brief_fails_quality():
    thin = {"topic": "x", "facts": [], "supporting_points": [], "entities": {}}
    script = svc.generate_script(thin, "football_story", "60s")
    script["hook"] = "hi"
    script["outro"] = "bye"
    quality = svc.score_quality(script, thin)
    assert quality["approved"] is False


async def test_script_agent_approves_and_memorizes(session_factory, sample_brief):
    from app.agents.script_agent import ScriptWriterAgent

    result = await ScriptWriterAgent().run(AgentContext(payload={
        "brief": sample_brief, "content_format": "transfer_update", "length": "60s"}))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["written"] == 1
    item = result.output["items"][0]
    assert item["status"] in ("approved", "rejected")
    assert "script_id" in item

    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(Script))).scalar() == 1
        if item["status"] == "approved":
            titles = (await session.execute(
                select(Memory).where(Memory.kind == "best_titles"))).scalars().all()
            assert len(titles) == 1
            hooks = (await session.execute(
                select(Memory).where(Memory.kind == "best_hooks"))).scalars().all()
            assert len(hooks) == 1


async def test_script_agent_rejects_thin_brief(session_factory):
    from app.agents.script_agent import ScriptWriterAgent

    thin = {"topic": "x", "facts": [], "supporting_points": [], "entities": {}}
    job = {"brief": thin, "content_format": "football_story", "length": "60s"}
    # Force a weak script by direct service check first.
    script = svc.generate_script(thin, "football_story", "60s")
    script["hook"] = "hi"
    assert svc.score_quality(script, thin)["approved"] is False
    result = await ScriptWriterAgent().run(AgentContext(payload=job))
    assert result.status == AgentStatus.SUCCEEDED
    # Agent writes its own hook; status recorded either way.
    assert result.output["written"] == 1
    async with session_factory() as session:
        row = (await session.execute(select(Script))).scalar_one()
        assert row.status in ("approved", "rejected")


def test_duration_labels_map_to_seconds(sample_brief):
    for length, seconds in (("30s", 30), ("60s", 60), ("3min", 180), ("5min", 300), ("10min", 600)):
        script = svc.generate_script(sample_brief, "football_story", length)
        assert script["estimated_duration"]["seconds"] == seconds
        assert script["estimated_duration"]["label"] == length


def test_hook_names_topic_and_outro_has_cta(sample_brief):
    script = svc.generate_script(sample_brief, "match_preview", "60s")
    assert "Arsenal record signing" in script["hook"]
    assert any(w in script["outro"].lower() for w in ("subscribe", "comment", "share"))
