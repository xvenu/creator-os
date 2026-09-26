"""Universal Production Director: best production strategy for each request.

Decision hierarchy (AI is always the last option):
  1. real footage / film_scene → 2. real photos / anime / product →
  3. licensed / brand → 4. public-domain → 5. AI (video/image/generated).

Content routing: `content_type` (video|anime|movie|ad|ai_film) selects
structure, default voice, preferred asset families, and render profile.
Pulse origin is never gated — ANY pulse may request ANY family.

Orchestrates rights_validation → reality_assets → voice_intelligence →
timeline_builder → production_strategy (+ ai_generation fallback).
Pure orchestration over injected candidates; the only I/O is none.
"""
from __future__ import annotations

from app.modules import ai_generation as ai_mod
from app.modules import content_types as ct_mod
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
    content_type = ct_mod.normalize(request.get("content_type", "video"))
    reqs = request.get("asset_requirements", {}) or {}
    real_required = bool(reqs.get("real_media_required", False))
    allow_ai_fill = reqs.get("allow_ai_fill", None)
    ai_allowed = effective_ai_allowed(mode, bool(request.get("ai_generation_allowed", False)))
    if real_required and mode != "AI_CREATIVE":
        ai_allowed = False
    if allow_ai_fill is False:
        ai_allowed = False

    # 1. Gather candidates: pulse sources + evidence + factory catalog rows.
    candidates = [assets_mod.normalize_source(s) for s in request.get("sources", [])]
    candidates += [assets_mod.normalize_evidence(e) for e in request.get("evidence", [])]
    candidates += [dict(c) for c in request.get("_catalog_assets", [])]

    # 2. Rights gate first — BLOCKED never proceeds; UNKNOWN flagged (excluded in REALITY_ONLY).
    rights_report = rights_mod.validate_batch(candidates, production_mode=mode)
    usable = [a for a in rights_report["usable"]
              if float(a.get("trust_score", 0.0)) >= min_trust or a.get("evidence_backed")]

    # 3. Hierarchy order: footage → photos/anime/product → licensed/brand → public → AI.
    usable = assets_mod.order(usable)
    # 3b. Content affinity: boost non-AI family kinds (stable, AI stays last).
    usable = _prefer_family_kinds(usable, content_type)
    # 3c. Pulse-declared preferred categories (official_photo, licensed_video…).
    usable = _prefer_required_categories(usable, reqs)

    # 4. Mode filtering (AI kinds, not just ai_generated).
    if mode == "REALITY_ONLY":
        usable = [a for a in usable if not assets_mod.is_ai(a)]
    elif not ai_allowed:
        usable = [a for a in usable if not assets_mod.is_ai(a)]
    elif mode == "AI_CREATIVE":
        usable = sorted(usable,
                        key=lambda a: (0 if assets_mod.is_ai(a) else 1,
                                       assets_mod.rank_key(a)))

    # 5. AI fallback: synthesize a placeholder AI asset only when allowed
    # and no usable real asset exists (AI is the last option, not the default).
    ai_injected = False
    if not usable and ai_allowed:
        usable = [ai_mod.synth_asset(
            f"factory: {content_type} ai-generated scene fill", 5.0)]
        ai_injected = True

    # 6. Voice (explicit > keyword signals > content default) + timeline + strategy.
    explicit_voice = (request.get("voice_profile", "") or "").strip()
    if explicit_voice:
        voice = voice_mod.match(explicit_voice, request.get("goal", ""),
                                request.get("style", ""), request.get("target_audience", ""))
    else:
        voice = voice_mod.match("", request.get("goal", ""),
                                request.get("style", ""), request.get("target_audience", ""))
        if voice.get("reason", "").startswith("no signal matched"):
            default = ct_mod.default_voice_for(content_type)
            if voice.get("profile") != default:
                voice = voice_mod.match(default, request.get("goal", ""),
                                        request.get("style", ""), request.get("target_audience", ""))
    narration = _narration(request)
    timeline = timeline_mod.build_for_content(
        narration, float(request.get("length_seconds", 0)), usable,
        content_type=content_type,
        call_to_action=request.get("call_to_action", ""))
    timeline["render_profile"] = ct_mod.render_profile_for(
        content_type, _ai_ratio(usable))
    from app.modules.renderer import media as media_mod
    _w, _h = media_mod.resolution_for(
        request.get("aspect_ratio", "16:9"), request.get("resolution", "1080p"),
        content_type)
    timeline["render_width"] = _w
    timeline["render_height"] = _h
    # AI generation prompts for gap scenes (plan only, no network).
    gaps = [s for s in timeline.get("scenes", []) if s.get("status") == "gap"]
    generation = ai_mod.generation_plan(
        request.get("goal", ""), request.get("style", ""),
        content_type, gaps, voice) if gaps and ai_allowed else {
            "content_type": content_type, "style_lock": "",
            "gap_count": len(gaps), "prompts": [],
            "provider": ai_mod.PROVIDERS[0]["name"]}
    request = {**request, "content_type": content_type}
    plan = strategy_mod.plan(request, usable, voice, timeline, ai_allowed)

    return {
        "production_mode": mode,
        "content_type": content_type,
        "structure": timeline.get("structure", "beats"),
        "render_profile": timeline.get("render_profile", ""),
        "ai_generation_allowed_effective": ai_allowed,
        "real_media_required": real_required,
        "real_media_honored": real_required and not ai_injected and not any(
            assets_mod.is_ai(a) for a in usable),
        "ai_fallback_injected": ai_injected,
        "generation_plan": generation,
        "assets": usable,
        "rights_report": rights_report["summary"],
        "blocked_assets": [b.get("source") for b in rights_report["blocked"]],
        "voice": voice,
        "timeline": timeline,
        "strategy": plan,
    }


def _ai_ratio(assets: list[dict]) -> float:
    if not assets:
        return 0.0
    ai = sum(1 for a in assets if assets_mod.is_ai(a))
    return round(ai / len(assets), 2)


def _prefer_family_kinds(assets: list[dict], content_type: str) -> list[dict]:
    """Stable boost for non-AI family kinds. AI never jumps the queue."""
    preferred = (ct_mod.spec(content_type).get("preferred_kinds") or [])
    preferred_non_ai = [k for k in preferred if k not in assets_mod.AI_KINDS]
    if not preferred_non_ai or content_type in ("video", "ai_film"):
        return assets
    pref = set(preferred_non_ai)
    return sorted(assets, key=lambda a: (
        0 if a.get("kind") in pref else 1, assets_mod.rank_key(a)))


def _prefer_required_categories(assets: list[dict], reqs: dict) -> list[dict]:
    """Boost pulse-declared preferred_types (categories). AI never jumps."""
    wanted = [str(t).lower() for t in (reqs.get("preferred_types") or [])]
    if not wanted:
        return assets
    def _hit(a: dict) -> bool:
        cat = str(a.get("category", "")).lower()
        kind = str(a.get("kind", "")).lower()
        return any(w in (cat, kind) for w in wanted)
    return sorted(assets, key=lambda a: (
        0 if (_hit(a) and not assets_mod.is_ai(a)) else 1, assets_mod.rank_key(a)))


def _narration(request: dict) -> str:
    for key in ("narration", "script", "voiceover_script"):
        val = request.get(key)
        if isinstance(val, str) and val.strip():
            base = val.strip()
            break
    else:
        goal = request.get("goal", "")
        evidence_texts = [str(e.get("text", "")) for e in request.get("evidence", [])
                          if e.get("text")]
        base = " ".join([goal, *evidence_texts]).strip() or goal or "Production narration."
    # Ads: brand line + CTA ride along as closing beats (production only).
    if ct_mod.normalize(request.get("content_type")) == "ad":
        extras = [request.get("brand_context", ""), request.get("call_to_action", "")]
        extras = [e.strip() for e in extras if isinstance(e, str) and e.strip()]
        for e in extras:
            if e not in base:
                base = f"{base} {e}".strip()
    return base
