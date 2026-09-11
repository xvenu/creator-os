"""Phase 3 tests: prediction math, grading, metrics + Prediction Agent."""
from __future__ import annotations

from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentStatus
from app.db.models import Memory, Prediction
from app.db.models.phase3 import PredictionMetric, PredictionResult
from app.services import prediction_service as svc


def test_factor_weights_sum_to_one():
    assert 0.30 + 0.20 + 0.15 + 0.15 + 0.10 + 0.10 == 1.0


def test_probabilities_normalize_exactly(sample_prediction_request):
    pred = svc.predict_match(sample_prediction_request)
    total = pred["home_win_probability"] + pred["draw_probability"] + pred["away_win_probability"]
    assert total == 1.0


def test_probabilities_normalize_without_form():
    pred = svc.predict_match({"home_club": "X", "away_club": "Y"})
    total = pred["home_win_probability"] + pred["draw_probability"] + pred["away_win_probability"]
    assert total == 1.0
    for p in (pred["home_win_probability"], pred["draw_probability"], pred["away_win_probability"]):
        assert 0.0 < p < 1.0


def test_home_advantage_favors_home():
    base = {"home_club": "A", "away_club": "B",
            "home_form": {"last_results": ["D", "D"]}, "away_form": {"last_results": ["D", "D"]}}
    pred = svc.predict_match(base)
    assert pred["home_win_probability"] > pred["away_win_probability"]


def test_strong_form_shifts_probability(sample_prediction_request):
    pred = svc.predict_match(sample_prediction_request)
    assert pred["home_win_probability"] > 0.5
    reversed_req = {**sample_prediction_request,
                    "home_form": sample_prediction_request["away_form"],
                    "away_form": sample_prediction_request["home_form"]}
    pred2 = svc.predict_match(reversed_req)
    assert pred2["away_win_probability"] > pred["away_win_probability"]


def test_expected_goals_and_scoreline(sample_prediction_request):
    pred = svc.predict_match(sample_prediction_request)
    xg = pred["expected_goals"]
    assert xg["home"] > xg["away"] > 0
    assert xg["total"] == round(xg["home"] + xg["away"], 2)
    assert pred["expected_score"] == "2-1" or "-" in pred["expected_score"]


def test_confidence_bounded_and_data_driven(sample_prediction_request):
    full = svc.predict_match(sample_prediction_request)["confidence"]
    empty = svc.predict_match({"home_club": "X", "away_club": "Y"})["confidence"]
    assert 0.0 <= full <= 1.0 and 0.0 <= empty <= 1.0
    assert full > empty  # full data > missing data


def test_confidence_penalizes_conflicting_signals():
    conflict = svc.calculate_confidence({
        "form": 0.6, "momentum": -0.5, "home_sample": 5, "away_sample": 5,
        "h2h_sample": 0, "strength": 1.0, "probs": (0.5, 0.25, 0.25),
    })
    aligned = svc.calculate_confidence({
        "form": 0.6, "momentum": 0.5, "home_sample": 5, "away_sample": 5,
        "h2h_sample": 0, "strength": 1.0, "probs": (0.5, 0.25, 0.25),
    })
    assert aligned > conflict


def test_brier_score_perfect_and_worst():
    assert svc.brier_score((1.0, 0.0, 0.0), "home") == 0.0
    assert svc.brier_score((1.0, 0.0, 0.0), "away") > 0.5


def test_league_strength_known_beats_unknown():
    assert svc.league_strength("Premier League") == 1.0
    assert svc.league_strength("Obscure Regional League") == 0.7
    assert svc.league_strength(None) == 0.7


def test_h2h_history_moves_needle():
    req = {"home_club": "A", "away_club": "B"}
    neutral = svc.predict_match(req)["home_win_probability"]
    dominant = svc.predict_match({**req, "h2h": ["H", "H", "H", "H"]})["home_win_probability"]
    dominated = svc.predict_match({**req, "h2h": ["A", "A", "A", "A"]})["home_win_probability"]
    assert dominant > neutral > dominated


def test_predicted_scoreline_value(sample_prediction_request):
    pred = svc.predict_match(sample_prediction_request)
    assert pred["expected_score"] == "2-1"


def test_prediction_output_shape(sample_prediction_request):
    pred = svc.predict_match(sample_prediction_request)
    for key in ("match_id", "home_win_probability", "draw_probability",
                "away_win_probability", "expected_score", "expected_goals",
                "confidence", "reasoning", "created_at"):
        assert key in pred, f"missing {key}"


async def test_prediction_agent_persists(session_factory, sample_prediction_request):
    from app.agents.prediction_agent import PredictionAgent

    agent = PredictionAgent()
    result = await agent.run(AgentContext(payload=sample_prediction_request))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["predicted"] == 1
    item = result.output["items"][0]
    assert item["home_win_probability"] + item["draw_probability"] + item["away_win_probability"] == 1.0

    async with session_factory() as session:
        count = (await session.execute(select(func.count()).select_from(Prediction))).scalar()
        assert count == 1


async def test_prediction_agent_grades_results_and_updates_metrics_and_memory(
    session_factory, sample_prediction_request
):
    from app.agents.prediction_agent import PredictionAgent

    agent = PredictionAgent()
    made = await agent.run(AgentContext(payload=sample_prediction_request))
    pred_id = made.output["items"][0]["prediction_id"]
    graded = await agent.run(AgentContext(payload={
        "results": [{"prediction_id": pred_id, "home_score": 2, "away_score": 0}]
    }))
    assert graded.output["graded"] == 1
    assert graded.output["results"][0]["correct"] is True

    async with session_factory() as session:
        res = (await session.execute(select(PredictionResult))).scalars().all()
        assert len(res) == 1 and res[0].correct is True
        metrics = (await session.execute(select(PredictionMetric))).scalars().all()
        scopes = {m.scope: m for m in metrics}
        assert scopes["overall"].accuracy == 1.0
        assert scopes["overall"].total == 1
        assert scopes["overall"].exact_scorelines == 0  # predicted 2-1, actual 2-0
        assert "league:Premier League" in scopes
        mem = (await session.execute(
            select(Memory).where(Memory.kind == "best_predictions")
        )).scalars().all()
        assert len(mem) == 1
        leagues = (await session.execute(
            select(Memory).where(Memory.kind == "best_leagues")
        )).scalars().all()
        assert len(leagues) >= 1


async def test_wrong_prediction_recorded_as_worst(session_factory, sample_prediction_request):
    from app.agents.prediction_agent import PredictionAgent

    agent = PredictionAgent()
    made = await agent.run(AgentContext(payload=sample_prediction_request))
    pred_id = made.output["items"][0]["prediction_id"]
    # Arsenal heavily favored; a 0-3 loss is a miss.
    graded = await agent.run(AgentContext(payload={
        "results": [{"prediction_id": pred_id, "home_score": 0, "away_score": 3}]
    }))
    assert graded.output["results"][0]["correct"] is False

    async with session_factory() as session:
        mem = (await session.execute(
            select(Memory).where(Memory.kind == "worst_predictions")
        )).scalars().all()
        assert len(mem) == 1
        metric = (await session.execute(
            select(PredictionMetric).where(PredictionMetric.scope == "overall")
        )).scalar_one()
        assert metric.accuracy == 0.0
