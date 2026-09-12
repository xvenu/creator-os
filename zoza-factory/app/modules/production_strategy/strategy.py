"""Production strategy engine: asset/voice/timeline/render strategy.

Given a validated Contract V2 request plus director-selected assets,
returns an explainable plan. Pure function — no I/O, no publishing.
"""
from __future__ import annotations


def plan(request: dict, selected_assets: list[dict], voice: dict,
         timeline: dict, effective_ai_allowed: bool) -> dict:
    real = [a for a in selected_assets if a.get("kind") != "ai_generated"]
    ai = [a for a in selected_assets if a.get("kind") == "ai_generated"]
    total = len(selected_assets) or 1
    reality_ratio = round(len(real) / total, 2)
    ai_ratio = round(len(ai) / total, 2)

    mode = request.get("production_mode", "REALITY_FIRST")
    strategy = _name(mode, reality_ratio, ai_ratio, effective_ai_allowed)
    length = float(request.get("length_seconds", 0))
    # Estimated factory runtime: base handling + per-scene render cost
    # (AI scenes cost ~2x real scenes). Deterministic estimate, not a promise.
    scenes = timeline.get("scene_count", 1) or 1
    estimated = round(5.0 + scenes * (2.0 + 3.0 * ai_ratio), 2)

    explanation = [
        f"mode={mode}; ai_generation_allowed(effective)={effective_ai_allowed}",
        f"selected {len(real)} real / {len(ai)} AI assets "
        f"(reality_ratio={reality_ratio}, ai_ratio={ai_ratio})",
        f"voice profile '{voice.get('profile')}' ({voice.get('tone')}, "
        f"{voice.get('pacing_wpm')} wpm, {voice.get('emotion')})",
        f"timeline: {timeline.get('scene_count')} scenes, "
        f"total {timeline.get('total_seconds')}s matches narration "
        f"({timeline.get('matches_narration')}); gaps={timeline.get('gap_count')}",
    ]
    return {
        "strategy": strategy,
        "reality_ratio": reality_ratio,
        "ai_ratio": ai_ratio,
        "asset_sources": [a.get("source", "") for a in selected_assets],
        "estimated_runtime": estimated,
        "explanation": explanation,
        "asset_strategy": _asset_strategy(mode, reality_ratio),
        "voice_strategy": voice.get("profile", "documentary"),
        "timeline_strategy": f"{timeline.get('scene_count', 0)} scenes / "
                             f"{timeline.get('total_seconds', 0)}s, word-weighted",
        "render_strategy": "simulated-1080p" if ai_ratio < 1.0 else "simulated-ai-1080p",
    }


def _name(mode: str, reality_ratio: float, ai_ratio: float,
          ai_allowed: bool) -> str:
    if mode == "REALITY_ONLY":
        return "reality-only"
    if mode == "AI_CREATIVE":
        return "ai-creative"
    if ai_ratio == 0.0:
        return "reality-first-full-reality" if mode == "REALITY_FIRST" else "hybrid-full-reality"
    if reality_ratio == 0.0:
        return "ai-fallback"
    return "reality-first-mixed" if mode == "REALITY_FIRST" else "hybrid-mix"


def _asset_strategy(mode: str, reality_ratio: float) -> str:
    if mode == "REALITY_ONLY":
        return "real assets exclusively; gaps stay visible, never AI-filled"
    if mode == "REALITY_FIRST":
        return ("real assets preferred; AI fills gaps only"
                if reality_ratio < 1.0 else "real assets cover all scenes")
    if mode == "HYBRID":
        return "balanced real/AI mix per scene mood"
    return "AI-led creative generation with real anchors where available"
