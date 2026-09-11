"""TransferService: source reputation, rumor scoring, probability, status machine.

All scoring is deterministic and documented for auditability.
"""
from __future__ import annotations

import datetime as dt

# Source reputation weights (0..1). Unknown sources default to 0.35.
SOURCE_REPUTATION: dict[str, float] = {
    "david ornstein": 0.97,
    "fabrizio romano": 0.9,
    "bbc sport": 0.9,
    "the athletic": 0.9,
    "sky sports": 0.85,
    "reuters": 0.85,
    "espn": 0.8,
    "guardian": 0.8,
    "l'equipe": 0.8,
    "marca": 0.65,
    "as": 0.6,
    "bild": 0.65,
    "gazzetta": 0.65,
    "goal": 0.55,
    "talksport": 0.5,
    "daily mail": 0.45,
    "the sun": 0.4,
    "caughtoffside": 0.25,
}

# Status → probability multiplier applied on top of credibility.
STATUS_MULTIPLIER: dict[str, float] = {
    "rumor": 0.7,
    "talks": 0.8,
    "advanced": 0.9,
    "medical": 0.95,
    "confirmed": 1.0,
    "collapsed": 0.0,
}

# Allowed status transitions (state machine).
TRANSITIONS: dict[str, set[str]] = {
    "rumor": {"talks", "advanced", "confirmed", "collapsed"},
    "talks": {"advanced", "medical", "confirmed", "collapsed", "rumor"},
    "advanced": {"medical", "confirmed", "collapsed", "talks"},
    "medical": {"confirmed", "collapsed"},
    "confirmed": set(),
    "collapsed": {"rumor"},
}

VALID_STATUSES = set(STATUS_MULTIPLIER)


def source_weight(source: str) -> float:
    key = source.strip().lower()
    for name, weight in SOURCE_REPUTATION.items():
        if name in key or key in name:
            return weight
    return 0.35


def score_rumor(sources: list[str]) -> tuple[float, float]:
    """(credibility, confidence) from source list.

    credibility = reputation-weighted mean + multi-source agreement boost
    (capped at 0.98). confidence grows with independent source count.
    """
    if not sources:
        return 0.0, 0.0
    weights = [source_weight(s) for s in sources]
    base = sum(weights) / len(weights)
    unique = len({s.strip().lower() for s in sources})
    agreement_boost = min((unique - 1) * 0.06, 0.15)
    credibility = round(min(base + agreement_boost, 0.98), 3)
    confidence = round(min(0.4 + unique * 0.15, 0.95), 3)
    return credibility, confidence


def generate_probability(credibility: float, status: str) -> float:
    """Transfer completion probability = credibility × status multiplier."""
    multiplier = STATUS_MULTIPLIER.get(status, 0.7)
    if status == "collapsed":
        return 0.0
    if status == "confirmed":
        return 1.0
    return round(max(0.0, min(credibility * multiplier, 0.99)), 3)


def update_transfer_status(current: str, new: str) -> str:
    """Validate a status transition; raises ValueError on illegal moves."""
    current = current.lower()
    new = new.lower()
    if new not in VALID_STATUSES:
        raise ValueError(f"Unknown transfer status: {new}")
    if new not in TRANSITIONS.get(current, set()):
        raise ValueError(f"Illegal transfer transition: {current} → {new}")
    return new


def build_timeline(existing: list[dict], status: str, note: str = "") -> list[dict]:
    entry = {
        "status": status,
        "note": note,
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    return [*existing, entry]


def normalize_player(name: str) -> str:
    return " ".join(name.strip().lower().split())


def cluster_rumors(rumors: list[dict]) -> list[dict]:
    """Group rumor dicts by (player, destination) → merged intelligence."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rumors:
        key = (normalize_player(str(r.get("player", ""))), str(r.get("to_club", "") or "").strip().lower())
        groups.setdefault(key, []).append(r)
    merged = []
    for (player_norm, _), members in groups.items():
        sources: list[str] = []
        for m in members:
            for s in m.get("sources", []):
                if s not in sources:
                    sources.append(s)
        credibility, confidence = score_rumor(sources)
        best = max(members, key=lambda m: str(m.get("status", "rumor")) in ("confirmed", "medical", "advanced"))
        merged.append(
            {
                "player": best.get("player", player_norm),
                "from_club": best.get("from_club"),
                "to_club": best.get("to_club"),
                "status": best.get("status", "rumor"),
                "credibility_score": credibility,
                "confidence": confidence,
                "probability": generate_probability(credibility, best.get("status", "rumor")),
                "sources": sources,
                "report_count": len(members),
            }
        )
    return sorted(merged, key=lambda m: m["probability"], reverse=True)


def process_rumor(rumor: dict) -> dict:
    """Score a single rumor input → transfer intelligence dict."""
    sources = list(rumor.get("sources", []))
    status = str(rumor.get("status", "rumor")).lower()
    if status not in VALID_STATUSES:
        raise ValueError(f"Unknown transfer status: {status}")
    credibility, confidence = score_rumor(sources)
    return {
        "player": str(rumor.get("player", "")).strip(),
        "from_club": rumor.get("from_club"),
        "to_club": rumor.get("to_club"),
        "status": status,
        "credibility_score": credibility,
        "confidence": confidence,
        "probability": generate_probability(credibility, status),
        "sources": sources,
        "last_updated": dt.datetime.now(dt.timezone.utc),
    }
