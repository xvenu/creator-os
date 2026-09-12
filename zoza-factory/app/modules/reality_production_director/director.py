"""Reality Production Director: best production strategy for each request.

Decision hierarchy (AI is always the last option):
  1. real footage → 2. real photos → 3. licensed → 4. public-domain → 5. AI.

Orchestrates rights_validation → reality_assets → voice_intelligence →
timeline_builder → production_strategy. Pure orchestration over injected
candidates; the only I/O is none — callers supply candidates and persist.
"""
from __future__ import annotations

from app.modules.production_strategy import strategy as strategy_mod
from app.modules.reality_assets import acquisition as assets_mod
from app.modules.rights_validation import validator as rights_mod
from app.modules.timeline_builder import builder as timeline_mod
from app.modules.voice_intelligence import voices as voice_mod


def effective_ai_allowed(production_mode: str, ai_generation_allowed: bool) -> bool:
    """Mode gate: REALITY_ONLY never allows AI; AI_CREATIVE always does."""
    if production_mode == "REALITY_ONLY":
        return False
    if production_mode in ("HYBRID", "AI_CREATIVE"):
        return True
    return bool(ai_generation_allowed)  # REALITY_FIRST honors the flag


def decide(request: dict, min_trust: float = 0.6) -> dict:
    """Full production decision for a Contract V2 request dict."""
    mode = request.get("production_mode", "REALITY_FIRST")
    ai_allowed = effective_ai_allowed(mode, bool(request.get("ai_generation_allowed", False)))

    # 1. Gather candidates: pulse sources + evidence + factory catalog rows.
    candidates = [assets_mod.normalize_source(s) for s in request.get("sources", [])]
    candidates += [assets_mod.normalize_evidence(e) for e in request.get("evidence", [])]
    candidates += [dict(c) for c in request.get("_catalog_assets", [])]

    # 2. Rights gate first — BLOCKED never proceeds; UNKNOWN flagged (excluded in REALITY_ONLY).
    rights_report = rights_mod.validate_batch(candidates, production_mode=mode)
    usable = [a for a in rights_report["usable"]
              if float(a.get("trust_score", 0.0)) >= min_trust or a.get("evidence_backed")]

    # 3. Hierarchy order: real footage → photos → licensed → public-domain → AI.
    usable = assets_mod.order(usable)

    # 4. Mode filtering.
    if mode == "REALITY_ONLY":
        usable = [a for a in usable if a.get("kind") != "ai_generated"]
    elif not ai_allowed:
        usable = [a for a in usable if a.get("kind") != "ai_generated"]
    elif mode == "AI_CREATIVE":
        usable = sorted(usable,
                        key=lambda a: (0 if a.get("kind") == "ai_generated" else 1,
                                       assets_mod.rank_key(a)))

    # 5. AI fallback: synthesize a placeholder AI asset only when allowed
    # and no usable real asset exists (AI is the last option, not the default).
    ai_injected = False
    if not usable and ai_allowed:
        usable = [assets_mod.manifest(
            source="factory: ai-generated scene fill", license="factory-generated",
            trust_score=0.5, rights_status="CLEARED",
            kind="ai_generated", category="generated", duration_seconds=5.0)]
        ai_injected = True

    # 6. Voice + timeline + strategy.
    voice = voice_mod.match(request.get("voice_profile", ""), request.get("goal", ""),
                            request.get("style", ""), request.get("target_audience", ""))
    narration = _narration(request)
    timeline = timeline_mod.build(narration, float(request.get("length_seconds", 0)), usable)
    plan = strategy_mod.plan(request, usable, voice, timeline, ai_allowed)

    return {
        "production_mode": mode,
        "ai_generation_allowed_effective": ai_allowed,
        "ai_fallback_injected": ai_injected,
        "assets": usable,
        "rights_report": rights_report["summary"],
        "blocked_assets": [b.get("source") for b in rights_report["blocked"]],
        "voice": voice,
        "timeline": timeline,
        "strategy": plan,
    }


def _narration(request: dict) -> str:
    for key in ("narration", "script", "voiceover_script"):
        val = request.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    goal = request.get("goal", "")
    evidence_texts = [str(e.get("text", "")) for e in request.get("evidence", [])
                      if e.get("text")]
    fallback = " ".join([goal, *evidence_texts]).strip()
    return fallback or goal or "Production narration."
