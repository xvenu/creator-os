"""Phase 2 tests: MatchAnalysisService + Match Analysis Agent."""
from __future__ import annotations

from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentStatus
from app.db.models.phase2 import MatchAnalysis
from app.services import match_analysis_service as svc


def test_analyze_team_form():
    form = svc.analyze_team_form("Arsenal", ["W", "W", "D", "W", "W"], 11, 3)
    assert form["form_string"] == "WWDWW"
    assert form["points"] == 13
    assert form["points_per_game"] == 2.6
    assert form["goal_difference"] == 8
    assert form["unbeaten"] is True


def test_analyze_team_form_empty():
    form = svc.analyze_team_form("X", [], 0, 0)
    assert form["form_string"] == "-"
    assert form["points_per_game"] == 0.0


def test_momentum_directions():
    home = svc.analyze_team_form("H", ["W", "W", "W"], 6, 1)
    away = svc.analyze_team_form("A", ["L", "L", "L"], 0, 6)
    assert svc.analyze_momentum(home, away)["direction"] == "home"
    assert svc.analyze_momentum(away, home)["direction"] == "away"
    even = svc.analyze_team_form("E", ["D", "D"], 2, 2)
    assert svc.analyze_momentum(even, even)["direction"] == "balanced"


def test_score_performance_ranks_scorer_top(sample_match):
    ratings = svc.score_performance(sample_match["events"])
    assert ratings[0]["player"] == "Bukayo Saka"
    assert ratings[0]["rating"] >= 8.0
    punished = next(r for r in ratings if r["player"] == "Enzo Fernandez")
    assert punished["rating"] < 6.5


def test_red_card_heavily_penalized():
    ratings = svc.score_performance([{"type": "red", "player": "John Doe"}])
    assert ratings[0]["rating"] <= 4.5


def test_tactical_patterns_goalless_draw():
    lines, strengths, _ = svc.extract_tactical_patterns([], 0, 0, "completed")
    assert any("stalemate" in line or "defensive" in line for line in lines)
    assert "defensive solidity" in strengths["home"]


def test_tactical_patterns_high_scoring():
    events = [
        {"type": "goal", "team": "home", "minute": 80},
        {"type": "goal", "team": "home", "minute": 88},
        {"type": "goal", "team": "away", "minute": 90},
    ]
    lines, strengths, weaknesses = svc.extract_tactical_patterns(events, 3, 2, "completed")
    assert any("late" in line.lower() or "open" in line.lower() for line in lines)
    assert weaknesses["home"] or weaknesses["away"]


def test_generate_narrative_names_clubs(sample_match):
    analysis = svc.analyze_match(sample_match)
    assert "Arsenal" in analysis["narrative"] and "Chelsea" in analysis["narrative"]


def test_analyze_match_output_shape(sample_match):
    analysis = svc.analyze_match(sample_match)
    for key in ("match_id", "key_events", "tactical_summary", "standout_players",
                "strengths", "weaknesses", "generated_at"):
        assert key in analysis, f"missing {key}"
    assert len(analysis["standout_players"]) > 0
    assert analysis["tactical_summary"]


async def test_match_agent_persists_analysis(session_factory, sample_match):
    from app.agents.match_agent import MatchAnalysisAgent

    agent = MatchAnalysisAgent()
    result = await agent.run(AgentContext(payload=sample_match))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["analyzed"] == 1
    item = result.output["items"][0]
    assert item["standout_players"][0]["player"] == "Bukayo Saka"

    async with session_factory() as session:
        count = (await session.execute(select(func.count()).select_from(MatchAnalysis))).scalar()
        assert count == 1
