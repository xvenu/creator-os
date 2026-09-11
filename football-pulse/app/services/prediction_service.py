"""PredictionService: match outcome engine + accuracy tracking.

Prediction factors (documented weights):
- recent form ............ 30%
- home advantage ......... 20%
- goal differential ...... 15%
- momentum ............... 15%
- league strength ........ 10%
- historical performance . 10%

Invariant: home + draw + away == 1.0 (renormalized after rounding).
"""
from __future__ import annotations

import datetime as dt
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Memory, Prediction
from app.db.models.phase3 import PredictionMetric, PredictionResult

MODEL_VERSION = "v0.3.0"
HOME_EDGE = 0.12  # base home-win probability boost before other factors

# League strength index (0..1): scales favorite separation + confidence.
LEAGUE_STRENGTH: dict[str, float] = {
    "premier league": 1.0,
    "la liga": 0.98,
    "serie a": 0.95,
    "bundesliga": 0.95,
    "ligue 1": 0.92,
    "champions league": 1.0,
    "world cup": 1.0,
    "euros": 0.98,
    "europa league": 0.88,
    "fa cup": 0.85,
    "copa america": 0.9,
    "nations league": 0.85,
}


def league_strength(league: str | None) -> float:
    if not league:
        return 0.7
    key = league.strip().lower()
    for name, strength in LEAGUE_STRENGTH.items():
        if name in key or key in name:
            return strength
    return 0.7


def _ppg(results: list[str]) -> float:
    clean = [r.upper() for r in results if r.upper() in ("W", "D", "L")][:5]
    if not clean:
        return 1.0  # neutral prior (below average, penalizes missing data)
    return sum({"W": 3, "D": 1, "L": 0}[r] for r in clean) / len(clean)


def _form_factor(home_results: list[str], away_results: list[str]) -> float:
    """-1..1 home-relative form edge. Weight: 30%."""
    return max(-1.0, min(((_ppg(home_results) - _ppg(away_results)) / 3.0), 1.0))


def _gd_factor(home_gd: int, away_gd: int) -> float:
    """-1..1 goal-difference edge (per-game scale of 5). Weight: 15%."""
    return max(-1.0, min(((home_gd - away_gd) / 5.0), 1.0))


def _momentum_factor(home_results: list[str], away_results: list[str]) -> float:
    """-1..1: last-2-results momentum vs full-5 form. Weight: 15%."""
    h_last2 = _ppg(home_results[:2]) if home_results else 1.0
    a_last2 = _ppg(away_results[:2]) if away_results else 1.0
    h_trend = (h_last2 - _ppg(home_results)) / 3.0
    a_trend = (a_last2 - _ppg(away_results)) / 3.0
    return max(-1.0, min((h_trend - a_trend), 1.0))


def _historical_factor(h2h: list[str]) -> float:
    """-1..1 from head-to-head: 'H' home win, 'D' draw, 'A' away win. Weight: 10%."""
    clean = [r.upper() for r in h2h if r.upper() in ("H", "D", "A")][:5]
    if not clean:
        return 0.0
    return (clean.count("H") - clean.count("A")) / len(clean)


def predict_match(request: dict) -> dict:
    """Full prediction → probabilities, xG, scoreline, confidence, reasoning."""
    home = str(request.get("home_club", "Home"))
    away = str(request.get("away_club", "Away"))
    league = request.get("league")
    home_form = request.get("home_form") or {}
    away_form = request.get("away_form") or {}
    home_results = list(home_form.get("last_results", []))
    away_results = list(away_form.get("last_results", []))
    home_gd = int(home_form.get("goals_for", 0)) - int(home_form.get("goals_against", 0))
    away_gd = int(away_form.get("goals_for", 0)) - int(away_form.get("goals_against", 0))
    h2h = list(request.get("h2h", []))
    strength = league_strength(league)

    form = _form_factor(home_results, away_results)
    gd = _gd_factor(home_gd, away_gd)
    momentum = _momentum_factor(home_results, away_results)
    hist = _historical_factor(h2h)

    # Weighted edge synthesis: home advantage is a fixed prior boost.
    edge = (
        0.30 * form
        + 0.20 * 1.0  # home advantage always favors home
        + 0.15 * gd
        + 0.15 * momentum
        + 0.10 * (strength - 0.7) * 2.0 * (1.0 if form >= 0 else -1.0) * 0.5
        + 0.10 * hist
    )
    # Base draw rate shrinks as edge grows (favorites draw less).
    draw_base = 0.27 * (1.0 - min(abs(edge), 0.8) * 0.5)
    home_raw = 0.44 + HOME_EDGE + edge * 0.55
    away_raw = 0.44 - edge * 0.45
    # Softmax-style normalization to exact 1.0.
    home_p, draw_p, away_p = _normalize(home_raw, draw_base, away_raw)

    xg_home, xg_away = calculate_expected_goals(home_form, away_form)
    scoreline = calculate_scoreline(xg_home, xg_away)
    confidence = calculate_confidence(
        {
            "form": form,
            "momentum": momentum,
            "edge": edge,
            "home_sample": len(home_results),
            "away_sample": len(away_results),
            "h2h_sample": len([r for r in h2h if str(r).upper() in ("H", "D", "A")]),
            "strength": strength,
            "probs": (home_p, draw_p, away_p),
        }
    )
    reasoning = (
        f"{home} vs {away}: form edge {form:+.2f}, goal-diff edge {gd:+.2f}, "
        f"momentum {momentum:+.2f}, h2h {hist:+.2f}, home advantage applied, "
        f"league strength {strength:.2f}."
    )
    return {
        "match_id": request.get("match_id"),
        "home_win_probability": home_p,
        "draw_probability": draw_p,
        "away_win_probability": away_p,
        "expected_score": scoreline,
        "expected_goals": {"home": xg_home, "away": xg_away, "total": round(xg_home + xg_away, 2)},
        "confidence": confidence,
        "reasoning": reasoning,
        "created_at": dt.datetime.now(dt.timezone.utc),
    }


def _normalize(home: float, draw: float, away: float) -> tuple[float, float, float]:
    """Normalize to sum exactly 1.0 (largest-remainder rounding to 3dp)."""
    total = home + draw + away
    raw = [max(home / total, 0.01), max(draw / total, 0.01), max(away / total, 0.01)]
    total = sum(raw)
    raw = [v / total for v in raw]
    floored = [math.floor(v * 1000) / 1000 for v in raw]
    remainder = round(1.0 - sum(floored), 3)
    # Award leftover thousandths to largest fractional parts.
    fracs = sorted(range(3), key=lambda i: (raw[i] * 1000) % 1, reverse=True)
    i = 0
    while remainder > 0.0005:
        floored[fracs[i % 3]] = round(floored[fracs[i % 3]] + 0.001, 3)
        remainder = round(remainder - 0.001, 3)
        i += 1
    return floored[0], floored[1], floored[2]


def calculate_expected_goals(home_form: dict, away_form: dict) -> tuple[float, float]:
    """Poisson-ish xG from attack/defense rates + home boost (+0.25/-0.10)."""
    def rate(form: dict, key: str, default: float) -> float:
        played = max(len(form.get("last_results", [])) or 0, 1)
        return float(form.get(key, default * played)) / played

    home_attack = rate(home_form, "goals_for", 1.4)
    home_defense = rate(home_form, "goals_against", 1.2)
    away_attack = rate(away_form, "goals_for", 1.2)
    away_defense = rate(away_form, "goals_against", 1.4)
    xg_home = max(round((home_attack + away_defense) / 2 + 0.25, 2), 0.1)
    xg_away = max(round((away_attack + home_defense) / 2 - 0.10, 2), 0.05)
    return xg_home, xg_away


def calculate_scoreline(xg_home: float, xg_away: float) -> str:
    return f"{max(int(round(xg_home)), 0)}-{max(int(round(xg_away)), 0)}"


def calculate_confidence(signals: dict) -> float:
    """0..1 confidence.

    Boosts: large samples, consistent edge|form alignment, decisive probs,
    strong league data. Penalties: missing data, conflicting form vs momentum,
    near-coin-flip probabilities.
    """
    conf = 0.55
    home_n = int(signals.get("home_sample", 0))
    away_n = int(signals.get("away_sample", 0))
    # Data quality: full 5-game samples both sides → +0.15; empty → −0.20.
    coverage = (min(home_n, 5) + min(away_n, 5)) / 10.0
    conf += (coverage - 0.5) * 0.3
    # h2h evidence.
    conf += min(int(signals.get("h2h_sample", 0)) * 0.02, 0.06)
    # Conflicting signals: form and momentum disagree → −0.10.
    form = float(signals.get("form", 0.0))
    momentum = float(signals.get("momentum", 0.0))
    if form * momentum < 0 and abs(form) > 0.2 and abs(momentum) > 0.2:
        conf -= 0.10
    # Decisiveness: max prob far from 1/3 → more confident.
    probs = signals.get("probs", (0.33, 0.34, 0.33))
    conf += (max(probs) - 1 / 3) * 0.6
    # League data quality.
    conf += (float(signals.get("strength", 0.7)) - 0.7) * 0.2
    return round(max(0.05, min(conf, 0.97)), 3)


def predicted_outcome_label(home_p: float, draw_p: float, away_p: float) -> str:
    if home_p >= draw_p and home_p >= away_p:
        return "home"
    if away_p >= draw_p:
        return "away"
    return "draw"


def actual_outcome_label(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def brier_score(probs: tuple[float, float, float], actual: str) -> float:
    """Mean squared error vs one-hot actual (home/draw/away order)."""
    actual_vec = {"home": (1, 0, 0), "draw": (0, 1, 0), "away": (0, 0, 1)}[actual]
    return round(sum((p - a) ** 2 for p, a in zip(probs, actual_vec)) / 3, 4)


async def record_prediction_result(
    session: AsyncSession,
    prediction: Prediction,
    actual_home: int,
    actual_away: int,
) -> PredictionResult:
    """Grade a prediction: update row, insert result, refresh metrics + memory."""
    actual = actual_outcome_label(actual_home, actual_away)
    predicted = predicted_outcome_label(
        prediction.home_win_prob, prediction.draw_prob, prediction.away_win_prob
    )
    correct = actual == predicted
    scoreline_exact = prediction.predicted_scoreline == f"{actual_home}-{actual_away}"
    brier = brier_score(
        (prediction.home_win_prob, prediction.draw_prob, prediction.away_win_prob), actual
    )
    prediction.outcome = actual
    prediction.correct = correct
    prediction.meta = {**(prediction.meta or {}), "actual_score": [actual_home, actual_away]}
    result = PredictionResult(
        prediction_id=prediction.id,
        actual_home_score=actual_home,
        actual_away_score=actual_away,
        actual_outcome=actual,
        predicted_outcome=predicted,
        correct=correct,
        scoreline_exact=scoreline_exact,
        brier_score=brier,
        meta={"model_version": prediction.model_version},
    )
    session.add(result)
    await session.flush()

    league = (prediction.meta or {}).get("league") or "unknown"
    await update_accuracy_metrics(session, "overall")
    await update_accuracy_metrics(session, f"league:{league}")

    # Memory: best/worst predictions + patterns.
    from app.services import memory_service

    label = (prediction.meta or {}).get("label") or str(prediction.id)
    pattern = (prediction.meta or {}).get("pattern") or "default"
    if correct:
        await memory_service.record_observation(
            session, "best_predictions", label, extra={"brier": brier}
        )
        await memory_service.record_observation(
            session, "best_prediction_patterns", pattern, extra={"league": league}
        )
    else:
        await memory_service.record_observation(
            session, "worst_predictions", label, extra={"brier": brier}
        )
    await memory_service.observe_graded_league_team(
        session, league, list((prediction.meta or {}).get("teams", [])), correct
    )
    await session.commit()
    await session.refresh(result)
    return result


async def update_accuracy_metrics(session: AsyncSession, scope: str) -> PredictionMetric:
    """Recompute rolling metrics for a scope from graded predictions."""
    if scope == "overall":
        stmt = select(Prediction).where(Prediction.correct.is_not(None))
        league_filter = None
    elif scope.startswith("league:"):
        league_filter = scope.split("league:", 1)[1]
        stmt = select(Prediction).where(Prediction.correct.is_not(None))
    else:
        stmt = select(Prediction).where(Prediction.correct.is_not(None))
        league_filter = None
    rows = (await session.execute(stmt)).scalars().all()
    if league_filter:
        rows = [r for r in rows if (r.meta or {}).get("league") == league_filter]
    total = len(rows)
    correct = sum(1 for r in rows if r.correct)
    exact = sum(
        1
        for r in rows
        if r.outcome is not None
        and r.predicted_scoreline == _actual_scoreline(r)
    )
    avg_conf = round(sum(r.confidence for r in rows) / total, 3) if total else 0.0
    briers = [
        brier_score((r.home_win_prob, r.draw_prob, r.away_win_prob), r.outcome)
        for r in rows
        if r.outcome
    ]
    brier_avg = round(sum(briers) / len(briers), 4) if briers else 0.0
    metric = (await session.execute(select(PredictionMetric).where(PredictionMetric.scope == scope))).scalar_one_or_none()
    if metric is None:
        metric = PredictionMetric(scope=scope)
        session.add(metric)
        await session.flush()
    metric.total = total
    metric.correct = correct
    metric.exact_scorelines = exact
    metric.accuracy = round(correct / total, 3) if total else 0.0
    metric.avg_confidence = avg_conf
    metric.brier_avg = brier_avg
    metric.meta = {"model_version": MODEL_VERSION}
    await session.flush()
    return metric


def _actual_scoreline(prediction: Prediction) -> str | None:
    scores = (prediction.meta or {}).get("actual_score")
    if not scores:
        return None
    return f"{scores[0]}-{scores[1]}"
