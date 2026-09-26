"""AI generation planning: prompts + provider abstraction (pure, no I/O).

The factory never calls external AI APIs directly in this phase — this
module decides WHAT should be generated (scene prompts, voice lines,
style lock) so a render provider can fulfill it. Keeps AI as the last
option: callers only invoke this when real assets leave gaps and the
effective AI gate is open.
"""
from __future__ import annotations

AI_ASSET_KINDS = ("ai_generated", "ai_video", "ai_image")

PROVIDERS = [{"name": "factory-synthetic", "available": True}]


def provider_availability() -> list[dict]:
    return [{"name": p["name"], "available": p["available"]} for p in PROVIDERS]


def is_ai_kind(kind: str) -> bool:
    return (kind or "") in AI_ASSET_KINDS


def generation_plan(goal: str, style: str, content_type: str,
                    gap_scenes: list[dict], voice: dict) -> dict:
    """Build per-gap synthetic prompts. Deterministic, no network."""
    ct = (content_type or "video").lower()
    style_lock = _style_lock(style, ct)
    prompts = []
    for scene in gap_scenes:
        nr = scene.get("narration", "")
        prompts.append({
            "scene_number": scene.get("scene_number"),
            "prompt": f"{style_lock} | scene: {nr[:160]}",
            "negative_prompt": "watermark, logo, photorealistic face of real person",
            "duration_seconds": scene.get("duration_seconds", 5.0),
            "voice_line": nr,
            "voice_profile": (voice or {}).get("profile", "documentary"),
        })
    return {
        "content_type": ct,
        "style_lock": style_lock,
        "gap_count": len(gap_scenes),
        "prompts": prompts,
        "provider": PROVIDERS[0]["name"],
    }


def _style_lock(style: str, content_type: str) -> str:
    base = (style or "").strip() or "cinematic"
    if content_type == "anime":
        return f"anime style, cel-shaded, dynamic keyframe composition, {base}"
    if content_type == "movie":
        return f"cinematic film still, 35mm depth, dramatic lighting, {base}"
    if content_type == "ad":
        return f"clean commercial product frame, high-key light, {base}"
    if content_type == "ai_film":
        return f"synthetic film frame, imaginative detail, {base}"
    return f"live-action documentary frame, natural light, {base}"


def synth_asset(source: str, duration_seconds: float = 5.0,
                kind: str = "ai_generated") -> dict:
    """Manifest fields for one synthetic fill asset (rights pre-cleared)."""
    from app.modules.reality_assets import acquisition as assets_mod
    k = kind if kind in AI_ASSET_KINDS else "ai_generated"
    return assets_mod.manifest(
        source=source, license="factory-generated",
        trust_score=0.5, rights_status="CLEARED",
        kind=k, category="generated",
        duration_seconds=float(duration_seconds))
