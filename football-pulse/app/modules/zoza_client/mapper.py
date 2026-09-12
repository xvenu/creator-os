"""Football Contract V2 mapping: native package -> Zoza Contract V2.

Canonical contract: zoza-factory/app/schemas/contract.py (ProductionRequestIn).
This module builds plain dicts only and validates via the canonical model
when importable. No second contract is defined here.
"""
from __future__ import annotations

import hashlib
import json

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
    """Pulse-owned decision. Explicit choice always wins."""
    if explicit is not None:
        mode = _norm_mode(explicit)
        if not mode:
            raise ValueError(f"unknown production mode: {explicit}")
        return mode
    for key in ("production_mode", "productionMode", "mode"):
        mode = _norm_mode(package.get(key))
        if mode:
            return mode
    ctype = str(package.get("content_type", package.get("type", ""))).lower()
    title = str(package.get("title", package.get("topic", ""))).lower()
    script = package.get("script", "")
    script_text = json.dumps(script).lower() if isinstance(script, dict) else str(script).lower()
    text = f"{ctype} {title} {script_text}"
    # The football Pulse decides whether real footage is necessary.
    if any(k in text for k in ("player interview", "press conference", "post-match interview")):
        return "REALITY_ONLY"
    if "highlight" in text:
        rights = str(package.get("rights_status", package.get("rights", ""))).lower()
        if rights in ("cleared", "licensed", "official"):
            return "REALITY_ONLY"
        return "REALITY_FIRST"
    if any(k in text for k in ("tactical breakdown", "tactics board", "diagram", "formation map")):
        return "HYBRID"
    if any(k in text for k in ("anime", "fictional", "fantasy xi", "what-if simulation")):
        if bool(package.get("ai_generation_allowed", False)):
            return "AI_CREATIVE"
        return "HYBRID"
    if any(k in text for k in ("biography", "history", "historical", "legend", "documentary")):
        return "REALITY_FIRST"
    return "REALITY_FIRST"


def _urgency(package: dict, override: str | None = None) -> str:
    if override and str(override).lower() in VALID_URGENCY:
        return str(override).lower()
    u = str(package.get("urgency", "")).lower()
    if u in VALID_URGENCY:
        return u
    ctype = str(package.get("content_type", "")).lower()
    meta = package.get("meta", {}) if isinstance(package.get("meta"), dict) else {}
    text = f"{package.get('title', '')} {package.get('topic', '')}".lower()
    if meta.get("breaking") or "breaking" in text or "done deal" in text:
        return "high"
    if ctype in ("transfer_update",) and float(package.get("opportunity_score", 0) or 0) >= 0.8:
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
    ctype = str(package.get("content_type", "")).lower()
    if ctype in ("documentary", "player_biography", "historical"):
        return 180
    if ctype in ("tactical_breakdown", "match_analysis"):
        return 120
    script = package.get("script", "")
    if isinstance(script, dict):
        words = len(" ".join(str(v) for v in script.values()).split())
    else:
        words = len(str(script).split())
    return 120 if words > 400 else 60


def _goal_style(package: dict) -> tuple[str, str]:
    ctype = str(package.get("content_type", package.get("type", "news"))).lower()
    title = str(package.get("title", package.get("topic", "football story")))
    if ctype in ("match_analysis", "match_recap"):
        return (f"match analysis: {title}".strip(), "sports analysis")
    if ctype in ("transfer_update", "transfer_news"):
        return (f"transfer news: {title}".strip(), "sports news")
    if ctype in ("player_biography", "biography"):
        return (f"player biography: {title}".strip(), "documentary")
    if ctype in ("tactical_breakdown", "tactics"):
        return (f"tactical breakdown: {title}".strip(), "analysis")
    if ctype in ("historical", "documentary", "legend"):
        return (f"historical football story: {title}".strip(), "documentary")
    if ctype in ("prediction", "preview"):
        return (f"match preview: {title}".strip(), "sports analysis")
    return (f"football story: {title}".strip(), "sports news")


def _sources_evidence(package: dict) -> tuple[list, list]:
    sources: list = []
    for key in ("sources", "references", "articles"):
        val = package.get(key, [])
        if isinstance(val, list):
            sources.extend(val)
    brief = package.get("brief", {})
    if isinstance(brief, dict):
        for f in brief.get("facts", []) if isinstance(brief.get("facts"), list) else []:
            sources.append({"source": str(f.get("source", "research-brief")),
                            "text": str(f.get("text", ""))})
    evidence: list = []
    for key in ("evidence", "facts"):
        val = package.get(key, [])
        if isinstance(val, list):
            evidence.extend(val)
    if isinstance(brief, dict) and isinstance(brief.get("facts"), list):
        evidence.extend(brief["facts"])
    intel = package.get("intel_items", [])
    if isinstance(intel, list):
        evidence.extend(intel)
    return sources, evidence


def build_asset_request(package: dict) -> dict | None:
    text = json.dumps(package, default=str).lower()
    want = bool(package.get("require_real_media", False))
    if not want and any(k in text for k in (
            "real footage", "match footage", "interview", "press conference",
            "stadium", "archive", "official")):
        want = True
    if str(package.get("content_type", "")).lower() in (
            "match_analysis", "player_biography", "historical", "documentary",
            "transfer_update", "transfer_news", "match_recap", "preview", "prediction"):
        want = True
    if not want:
        return None
    subject = str(package.get("topic", package.get("title", "match")) or "match")
    return {
        "type": "real_world_asset_request",
        "subject": subject,
        "require_real_media": True,
        "preferred_assets": [
            "licensed_match_footage",
            "official_interviews",
            "press_conference_clips",
            "public_domain_archive",
        ],
    }


def _voice_audience(package: dict) -> tuple[str, str]:
    voice = str(package.get("voice_profile", "") or
                (package.get("voice_requirements", {}) or {}).get("style", "") or
                "energetic")
    regions = package.get("target_regions", package.get("regions", []))
    if isinstance(regions, list) and regions:
        first = regions[0]
        audience = str(first.get("region") if isinstance(first, dict) else first)
    else:
        audience = str(package.get("target_audience", "global"))
    return voice, audience or "global"


def map_package_to_contract(package: dict, *,
                            production_mode: str | None = None,
                            urgency: str | None = None,
                            length_seconds: int | None = None,
                            ai_generation_allowed: bool | None = None,
                            request_id: str | None = None) -> dict:
    if not package.get("package_id") and not package.get("id") and not package.get("topic"):
        raise ValueError("package missing identity (package_id/id/topic)")
    if not package.get("title") and not package.get("topic"):
        raise ValueError("package missing title/topic")
    goal, style = _goal_style(package)
    mode = decide_production_mode(package, production_mode)
    urg = _urgency(package, urgency)
    length = _length(package, length_seconds)
    if ai_generation_allowed is None:
        ai_allowed = bool(package.get("ai_generation_allowed", mode in ("HYBRID", "AI_CREATIVE")))
    else:
        ai_allowed = bool(ai_generation_allowed)
    sources, evidence = _sources_evidence(package)
    asset_req = build_asset_request(package)
    if asset_req is not None:
        sources = [*sources, asset_req]
    voice, audience = _voice_audience(package)
    try:
        priority = int(float(package.get("priority", package.get("opportunity_score", 0) or 0)
                             if float(package.get("opportunity_score", 0) or 0) <= 1
                             else package.get("priority", 50)))
        if float(package.get("opportunity_score", 0) or 0) <= 1 and "opportunity_score" in package:
            priority = int(float(package["opportunity_score"]) * 100)
    except (TypeError, ValueError):
        priority = 0
    priority = max(0, min(100, priority))
    pid = str(package.get("package_id", package.get("id", package.get("topic"))))
    fp_raw = json.dumps([goal, style, length, urg, mode, ai_allowed, voice, audience],
                        sort_keys=True)
    fp = hashlib.sha1(fp_raw.encode()).hexdigest()[:8]
    rid = request_id or f"fz-{pid[:12]}-{fp}"
    contract = {
        "request_id": rid,
        "pulse": "football-pulse",
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
    try:
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[5]  # football-pulse/..
        fac = root / "zoza-factory"
        if str(fac) not in sys.path:
            sys.path.insert(0, str(fac))
        from app.schemas.contract import ProductionRequestIn  # type: ignore
        ProductionRequestIn(**payload)
        return payload
    except Exception as exc:
        missing = [k for k in REQUIRED_CONTRACT_FIELDS if k not in payload]
        if missing:
            raise ValueError(f"contract missing fields: {missing}") from exc
        return payload


class FootballProductionMapper:
    def decide_mode(self, package: dict, explicit: str | None = None) -> str:
        return decide_production_mode(package, explicit)

    def asset_request(self, package: dict) -> dict | None:
        return build_asset_request(package)

    def to_contract(self, package: dict, **overrides) -> dict:
        return validate_against_canonical(map_package_to_contract(package, **overrides))
