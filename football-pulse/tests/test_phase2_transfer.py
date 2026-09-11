"""Phase 2 tests: TransferService + Transfer Intelligence Agent."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentStatus
from app.db.models.phase2 import TransferIntel
from app.services import transfer_service as svc


def test_source_weight_known_beats_unknown():
    assert svc.source_weight("David Ornstein") > svc.source_weight("Random ITK Blog")
    assert svc.source_weight("Fabrizio Romano") >= 0.9


def test_score_rumor_multi_source_boost():
    single, _ = svc.score_rumor(["The Sun"])
    multi, _ = svc.score_rumor(["David Ornstein", "BBC Sport", "Sky Sports"])
    assert multi > single
    assert 0.0 <= multi <= 1.0


def test_score_rumor_empty():
    assert svc.score_rumor([]) == (0.0, 0.0)


def test_generate_probability_status_ladder():
    assert svc.generate_probability(0.8, "confirmed") == 1.0
    assert svc.generate_probability(0.9, "collapsed") == 0.0
    rumor = svc.generate_probability(0.8, "rumor")
    talks = svc.generate_probability(0.8, "talks")
    assert 0.0 < rumor < talks < 1.0


def test_update_transfer_status_legal_and_illegal():
    assert svc.update_transfer_status("rumor", "talks") == "talks"
    assert svc.update_transfer_status("medical", "confirmed") == "confirmed"
    with pytest.raises(ValueError):
        svc.update_transfer_status("confirmed", "rumor")
    with pytest.raises(ValueError):
        svc.update_transfer_status("rumor", "nonsense")


def test_cluster_rumors_merges_same_destination(sample_rumors):
    merged = svc.cluster_rumors(sample_rumors)
    assert len(merged) == 1
    assert merged[0]["report_count"] == 2
    assert len(merged[0]["sources"]) == 3


def test_process_rumor_output_shape():
    intel = svc.process_rumor({
        "player": "Victor Osimhen", "from_club": "Napoli",
        "to_club": "Arsenal", "sources": ["David Ornstein"], "status": "talks",
    })
    for key in ("player", "from_club", "to_club", "status", "credibility_score",
                "confidence", "sources", "last_updated"):
        assert key in intel, f"missing {key}"
    assert intel["probability"] > 0.5


async def test_transfer_agent_upserts_and_merges(session_factory, sample_rumors):
    from app.agents.transfer_agent import TransferIntelligenceAgent

    agent = TransferIntelligenceAgent()
    result = await agent.run(AgentContext(payload={"rumors": sample_rumors}))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["processed"] == 2

    async with session_factory() as session:
        rows = (await session.execute(select(TransferIntel))).scalars().all()
        # Same player+destination merged into one tracking row.
        assert len(rows) == 1
        assert len(rows[0].sources) == 3
        assert rows[0].probability > 0.5
        assert len(rows[0].timeline) == 2
