"""Music production mapping: native MusicPulse package -> Zoza Contract V2.

Canonical contract lives in zoza-factory/app/schemas/contract.py
(ProductionRequestIn). This module never redefines that schema — it only
builds plain dicts with the required fields and validates by importing the
canonical model when available.
"""
from __future__ import annotations

import hashlib
import json

# Canonical field set (mirrors ProductionRequestIn field names, not a schema).
REQUIRED_CONTRACT_FIELDS = (
    "request_id",
    "goal",
    "style",
    "length_seconds",
    "urgency",
    "production_mode",
    "ai_generation_allowed",
    "sources",
    "evidence",
    "voice_profile",
    "target_audience",
    "priority",
)

VALID_MODES = ("REALITY_ONLY", "REALITY_FIRST", "HYBRID", "AI_CREATIVE")
# Spec shorthand "FIRST" always means REALITY_FIRST.
MODE_ALIASES = {"FIRST": "REALITY_FIRST", "REALITY_FIRST": "REALITY_FIRST",
                "REALITY_ONLY": "REALITY_ONLY", "HYBRID": "HYBRID",
                "AI_CREATIVE": "AI_CREATIVE"}
VALID_URGENCY = ("low", "normal", "high", "breaking")


def _norm_mode(value: str | None) -> str | None:
    if not value:
        return None
    v = str(value).strip().upper()
    v = MODE_ALIASES.get(v, v)
    return v if v in VALID_MODES else None


def decide_production_mode(package: dict, explicit: str | None = None) -> str:
    """Pulse-owned decision. Explicit choice always wins; never hard-coded."""
    if explicit is not None:
        mode = _norm_mode(explicit)
        if not mode:
            raise ValueError(f"unknown production mode: {explicit}")
        return mode
    for key in ("production_mode", "productionMode", "mode"):
        mode = _norm_mode(package.get(key))
        if mode:
            return mode
    ptype = str(package.get("type", package.get("content_type", ""))).lower()
    title = str(package.get("title", "")).lower()
    brief = str(package.get("video_brief", "")).lower()
    text = f"{ptype} {title} {brief}"
    # Real interview / live performance -> strict reality.
    if any(k in text for k in ("interview", "live performance", "press conference")):
        return "REALITY_ONLY"
    # Current highlights where rights are cleared -> reality only.
    if "highlight" in text and str(package.get("rights_status", "")).lower() == "cleared":
        return "REALITY_ONLY"
    # Fictional / anime concept -> AI creative.
    if any(k in text for k in ("anime", "fictional", "concept video", "ai concept")):
        if bool(package.get("ai_generation_allowed", False)):
            return "AI_CREATIVE"
        return "HYBRID"
    # Explainer needing diagrams/graphics -> hybrid.
    if ptype in ("explainer", "ranking", "review") or "diagram" in brief or "infographic" in brief:
        return "HYBRID"
    # Historical / biography / documentary -> reality-first.
    if ptype in ("documentary", "profile", "breakout_report"):
        return "REALITY_FIRST"
    return "REALITY_FIRST"


def _urgency(package: dict, override: str | None = None) -> str:
    if override and str(override).lower() in VALID_URGENCY:
        return str(override).lower()
    u = str(package.get("urgency", "")).lower()
    if u in VALID_URGENCY:
        return u
    title = str(package.get("title", "")).lower()
    ptype = str(package.get("type", "")).lower()
    if any(k in title for k in ("breaking", "just happened", "exclusive")):
        return "high"
    if ptype in ("news", "trend_report") and float(package.get("priority_score", 0) or 0) >= 85:
        return "high"
    return "normal"


def _length(package: dict, override: int | None = None) -> int:
    if override:
        return max(1, min(3600, int(override)))
    if package.get("length_seconds"):
        try:
            return max(1, min(3600, int(package["length_seconds"])))
        except (TypeError, ValueError):
            pass
    ptype = str(package.get("type", package.get("content_type", ""))).lower()
    script = str(package.get("script", ""))
    words = len(script.split())
    if ptype == "documentary":
        return 180
    if ptype in ("profile", "breakout_report"):
        return 120
    if words > 400:
        return 120
    return 60


def _goal_style(package: dict) -> tuple[str, str]:
    ptype = str(package.get("type", package.get("content_type", "news"))).lower()
    title = str(package.get("title", ""))
    if ptype == "news":
        # Longer news pieces lean documentary; short hits stay news.
        style = "documentary" if len(str(package.get("script", ""))) > 1200 else "news"
        return (f"news video: {title}".strip(), style)
    if ptype == "profile":
        return (f"artist history: {title}".strip(), "documentary")
    if ptype == "documentary":
        return (f"music documentary: {title}".strip(), "documentary")
    if ptype == "review":
        return (f"music review: {title}".strip(), "explainer")
    if ptype == "ranking":
        return (f"music ranking: {title}".strip(), "explainer")
    if ptype in ("explainer", "trend_report", "breakout_report"):
        return (f"{ptype}: {title}".strip(), "explainer")
    return (f"{ptype or 'news video'}: {title}".strip(), "news")


def build_asset_request(package: dict) -> dict | None:
    """Real-world asset hint. Zoza still validates rights; never bypassed."""
    want_real = bool(package.get("require_real_media", False))
    brief = str(package.get("video_brief", "")).lower()
    ptype = str(package.get("type", "")).lower()
    if not want_real:
        if ptype in ("documentary", "profile", "news", "breakout_report"):
            want_real = True
        elif any(k in brief for k in ("interview", "concert", "archive", "official")):
            want_real = True
    if not want_real:
        return None
    subject = str(package.get("artist", package.get("topic", "artist")) or "artist")
    return {
        "type": "real_world_asset_request",
        "subject": subject,
        "require_real_media": True,
        "preferred_assets": [
            "official_photos",
            "licensed_video",
            "official_interviews",
            "public_domain_archive",
        ],
    }


def _content_key(package: dict) -> str:
    pid = str(package.get("id", package.get("package_id", "unknown")))
    return pid


def _production_fingerprint(goal: str, style: str, length: int, urgency: str,
                            mode: str, ai_allowed: bool, voice: str,
                            audience: str) -> str:
    raw = json.dumps([goal, style, length, urgency, mode, ai_allowed, voice, audience],
                     sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:8]


def map_package_to_contract(package: dict, *,
                            production_mode: str | None = None,
                            urgency: str | None = None,
                            length_seconds: int | None = None,
                            ai_generation_allowed: bool | None = None,
                            request_id: str | None = None) -> dict:
    """Translate an existing package into Contract V2 fields. No invented content."""
    if not package.get("id") and not package.get("package_id"):
        raise ValueError("package missing id")
    if not package.get("title"):
        raise ValueError("package missing title")
    goal, style = _goal_style(package)
    mode = decide_production_mode(package, production_mode)
    urg = _urgency(package, urgency)
    length = _length(package, length_seconds)
    if ai_generation_allowed is None:
        ai_allowed = bool(package.get("ai_generation_allowed", mode in ("HYBRID", "AI_CREATIVE")))
    else:
        ai_allowed = bool(ai_generation_allowed)
    sources = list(package.get("sources", []) or [])
    evidence = list(package.get("evidence", []) or [])
    asset_req = build_asset_request(package)
    if asset_req is not None:
        sources = [*sources, asset_req]
    voice = str(package.get("voice_profile", package.get("voice", "")) or
                ("news" if style == "news" else "documentary"))
    audience = str(package.get("target_audience", package.get("target_market", "general")) or "general")
    try:
        priority = int(float(package.get("priority", package.get("priority_score", 0) or 0)))
    except (TypeError, ValueError):
        priority = 0
    priority = max(0, min(100, priority))
    pid = _content_key(package)
    fp = _production_fingerprint(goal, style, length, urg, mode, ai_allowed, voice, audience)
    rid = request_id or f"mz-{pid[:12]}-{fp}"
    contract = {
        "request_id": rid,
        "pulse": "music-pulse",
        "goal": goal,
        "style": style,
        "length_seconds": length,
        "urgency": urg,
        "production_mode": mode,
        "ai_generation_allowed": ai_allowed,
        "sources": sources,
        "evidence": evidence,
        "voice_profile": voice,
        "target_audience": audience,
        "priority": priority,
    }
    missing = [k for k in REQUIRED_CONTRACT_FIELDS if k not in contract]
    if missing:  # pragma: no cover - defensive
        raise ValueError(f"contract mapping missing fields: {missing}")
    return contract


def validate_against_canonical(payload: dict) -> dict:
    """Validate via the canonical factory model when importable (no second contract)."""
    try:
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[5]  # music-pulse/..
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from zoza_factory_schemas import contract as _c  # type: ignore
        _c.ProductionRequestIn(**payload)
        return payload
    except ImportError:
        pass
    try:
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[5]
        fac = root / "zoza-factory"
        if str(fac) not in sys.path:
            sys.path.insert(0, str(fac))
        from app.schemas.contract import ProductionRequestIn  # type: ignore
        ProductionRequestIn(**payload)
        return payload
    except Exception as exc:
        # Fall back to required-field check so the pulse stays buildable offline.
        missing = [k for k in REQUIRED_CONTRACT_FIELDS if k not in payload]
        if missing:
            raise ValueError(f"contract missing fields: {missing}") from exc
        return payload


class MusicProductionMapper:
    """Namespace wrapper (spec name) over the mapping functions."""

    def decide_mode(self, package: dict, explicit: str | None = None) -> str:
        return decide_production_mode(package, explicit)

    def asset_request(self, package: dict) -> dict | None:
        return build_asset_request(package)

    def to_contract(self, package: dict, **overrides) -> dict:
        payload = map_package_to_contract(package, **overrides)
        return validate_against_canonical(payload)
