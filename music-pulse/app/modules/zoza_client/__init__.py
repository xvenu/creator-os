"""MusicPulse zoza_client: thin Contract V2 caller-side adapter.

MusicPulse decides WHAT/WHY/audience/region/urgency/mode/AI-allowed.
Zoza Factory decides HOW (assets, rights, voice, timeline, render, QC).

This package never renders (no ffmpeg/providers) and never publishes.
It only maps native packages -> Contract V2 dicts, submits idempotently,
tracks factory state, and returns validated exports for Pulse publishing.
"""
from app.modules.zoza_client.adapter import MusicZozaAdapter
from app.modules.zoza_client.mapper import (
    MusicProductionMapper,
    build_asset_request,
    decide_production_mode,
    map_package_to_contract,
)
from app.modules.zoza_client.tracker import MusicZozaTracker

def register_with_creator_os(pulse: str = "music-pulse") -> dict:
    """Fail-open Creator-OS registration. Observability only, never blocks."""
    try:
        from app.core.shared import network_orchestrator as orch
        orch.register_pulse(pulse, ["news", "documentary", "explainer",
                                    "REALITY_ONLY", "REALITY_FIRST", "HYBRID", "AI_CREATIVE"])
        orch.heartbeat(pulse, "healthy")
        return {"registered": pulse}
    except Exception:
        return {"registered": pulse, "shared_unavailable": True}


__all__ = [
    "MusicZozaAdapter",
    "MusicProductionMapper",
    "MusicZozaTracker",
    "build_asset_request",
    "decide_production_mode",
    "map_package_to_contract",
    "register_with_creator_os",
]
