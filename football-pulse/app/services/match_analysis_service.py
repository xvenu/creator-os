"""MatchAnalysisService: form, momentum, performance scoring, narratives.

Deterministic rule-based analysis over structured match inputs.
"""
from __future__ import annotations

import datetime as dt

POINTS = {"W": 3, "D": 1, "L": 0}


def analyze_team_form(
    club: str,
    last_results: list[str],
    goals_for: int = 0,
    goals_against: int = 0,
) -> dict:
    """Form summary over the last N results (W/D/L strings)."""
    clean = [r.upper() for r in last_results if r.upper() in POINTS][:5]
    played = len(clean) or 1
    points = sum(POINTS[r] for r in clean)
    return {
        "club": club,
        "form_string": "".join(clean) if clean else "-",
        "played": len(clean),
        "points": points,
        "points_per_game": round(points / played, 2),
        "wins": clean.count("W"),
        "draws": clean.count("D"),
        "losses": clean.count("L"),
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goal_difference": goals_for - goals_against,
        "unbeaten": all(r != "L" for r in clean) if clean else False,
        "winless": all(r != "W" for r in clean) if clean else False,
    }


def analyze_momentum(home_form: dict, away_form: dict) -> dict:
    """Compare two form dicts → momentum direction + margin."""
    diff = round(home_form.get("points_per_game", 0.0) - away_form.get("points_per_game", 0.0), 2)
    if diff >= 0.6:
        direction = "home"
    elif diff <= -0.6:
        direction = "away"
    else:
        direction = "balanced"
    return {"direction": direction, "ppg_margin": diff}


def score_performance(events: list[dict]) -> list[dict]:
    """Per-player ratings from key events. Base 6.5, clamped 1..10.

    Event weights: goal +1.5, assist +1.0, penalty_scored +1.2,
    clean_sheet +0.8 (GK/DEF), yellow -0.4, red -2.0, own_goal -1.5,
    penalty_missed -1.0, save +0.3 (capped).
    """
    ratings: dict[str, dict] = {}
    saves: dict[str, int] = {}

    def entry(player: str) -> dict:
        return ratings.setdefault(player, {"player": player, "rating": 6.5, "contributions": []})

    for ev in events:
        kind = str(ev.get("type", "")).lower()
        player = str(ev.get("player", "Unknown"))
        e = entry(player)
        if kind == "goal":
            e["rating"] += 1.5
            e["contributions"].append("goal")
        elif kind == "assist":
            e["rating"] += 1.0
            e["contributions"].append("assist")
        elif kind == "penalty_scored":
            e["rating"] += 1.2
            e["contributions"].append("penalty")
        elif kind == "penalty_missed":
            e["rating"] -= 1.0
            e["contributions"].append("penalty missed")
        elif kind == "yellow":
            e["rating"] -= 0.4
        elif kind == "red":
            e["rating"] -= 2.0
            e["contributions"].append("sent off")
        elif kind == "own_goal":
            e["rating"] -= 1.5
        elif kind == "save":
            saves[player] = saves.get(player, 0) + 1
        elif kind == "clean_sheet":
            e["rating"] += 0.8
            e["contributions"].append("clean sheet")

    for player, count in saves.items():
        entry(player)["rating"] += min(count * 0.3, 1.5)
        if count >= 3:
            entry(player)["contributions"].append(f"{count} saves")

    out = [
        {"player": p, "rating": round(max(1.0, min(v["rating"], 10.0)), 1), "contributions": v["contributions"]}
        for p, v in ratings.items()
    ]
    return sorted(out, key=lambda r: r["rating"], reverse=True)


def extract_tactical_patterns(
    events: list[dict],
    home_score: int | None,
    away_score: int | None,
    status: str,
) -> tuple[list[str], dict, dict]:
    """Rule-based tactical observations → (summary_lines, strengths, weaknesses)."""
    lines: list[str] = []
    strengths: dict[str, list[str]] = {"home": [], "away": []}
    weaknesses: dict[str, list[str]] = {"home": [], "away": []}

    by_team: dict[str, list[dict]] = {"home": [], "away": []}
    for ev in events:
        team = "home" if str(ev.get("team", "home")).lower() == "home" else "away"
        by_team[team].append(ev)

    for side in ("home", "away"):
        goals = [e for e in by_team[side] if str(e.get("type", "")).lower() in ("goal", "penalty_scored")]
        minutes = [int(e.get("minute", 0) or 0) for e in goals]
        late = [m for m in minutes if m >= 75]
        early = [m for m in minutes if 0 < m <= 15]
        if len(goals) >= 2:
            lines.append(f"{side.title()} side showed strong attacking output ({len(goals)} goals).")
            strengths[side].append("attacking output")
        if late:
            lines.append(f"{side.title()} side finished strongly with {len(late)} late goal(s).")
            strengths[side].append("late-game fitness")
        if early:
            lines.append(f"{side.title()} side started on the front foot (early goal).")
            strengths[side].append("fast starts")
        reds = [e for e in by_team[side] if str(e.get("type", "")).lower() == "red"]
        if reds:
            lines.append(f"{side.title()} side must address discipline after a red card.")
            weaknesses[side].append("discipline")

    if status == "completed" and home_score is not None and away_score is not None:
        total = home_score + away_score
        if total == 0:
            lines.append("A stalemate defined by defensive organization on both sides.")
            strengths["home"].append("defensive solidity")
            strengths["away"].append("defensive solidity")
        elif total >= 4:
            lines.append("An open, high-scoring contest with transitional chances at both ends.")
            weaknesses["home"].append("defensive transitions")
            weaknesses["away"].append("defensive transitions")
        if home_score > away_score:
            lines.append("Home advantage proved decisive.")
        elif away_score > home_score:
            lines.append("The away side handled a hostile environment impressively.")

    if not lines:
        lines.append("A balanced tactical battle with limited clear-cut separation between the sides.")
    return lines, strengths, weaknesses


def generate_narrative(
    home_club: str,
    away_club: str,
    league: str | None,
    status: str,
    home_score: int | None,
    away_score: int | None,
    momentum: dict,
    standout: list[dict],
) -> str:
    comp = f" in the {league}" if league else ""
    if status == "completed" and home_score is not None and away_score is not None:
        base = f"{home_club} {home_score}-{away_score} {away_club}{comp}. "
    else:
        base = f"{home_club} host {away_club}{comp} in a fascinating tactical matchup. "
    direction = momentum.get("direction", "balanced")
    if direction == "home":
        base += f"{home_club} arrive with superior momentum. "
    elif direction == "away":
        base += f"{away_club} arrive with superior momentum. "
    else:
        base += "Little separates the sides on recent form. "
    if standout:
        top = standout[0]
        base += f"Key figure: {top['player']} (rated {top['rating']})."
    return base.strip()


def analyze_match(request: dict) -> dict:
    """Full match analysis → structured intelligence dict."""
    home = str(request.get("home_club", "Home"))
    away = str(request.get("away_club", "Away"))
    league = request.get("league")
    status = str(request.get("status", "upcoming"))
    home_score = request.get("home_score")
    away_score = request.get("away_score")
    events: list[dict] = list(request.get("events", []))

    home_form_in = request.get("home_form") or {}
    away_form_in = request.get("away_form") or {}
    home_form = analyze_team_form(
        home,
        list(home_form_in.get("last_results", [])),
        int(home_form_in.get("goals_for", 0)),
        int(home_form_in.get("goals_against", 0)),
    )
    away_form = analyze_team_form(
        away,
        list(away_form_in.get("last_results", [])),
        int(away_form_in.get("goals_for", 0)),
        int(away_form_in.get("goals_against", 0)),
    )
    momentum = analyze_momentum(home_form, away_form)
    standout = score_performance(events)
    summary_lines, strengths, weaknesses = extract_tactical_patterns(events, home_score, away_score, status)
    narrative = generate_narrative(home, away, league, status, home_score, away_score, momentum, standout)
    return {
        "match_id": request.get("match_id"),
        "key_events": events,
        "tactical_summary": " ".join(summary_lines),
        "standout_players": standout[:5],
        "strengths": strengths,
        "weaknesses": weaknesses,
        "momentum": momentum,
        "form": {"home": home_form, "away": away_form},
        "narrative": narrative,
        "generated_at": dt.datetime.now(dt.timezone.utc),
    }
