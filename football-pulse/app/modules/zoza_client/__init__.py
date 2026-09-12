"""Zoza client: FootballPulse → Zoza Video Factory bridge.

FootballPulse owns intelligence → packages → publishing → revenue.
It never renders. This module submits packages to the factory, tracks
factory jobs, collects contract-validated exports, and retries failures.

Factory addressing mirrors the Creator-OS convention (same as music-pulse):
$ZOZA_DIR/jobs/*.json file queue, defaulting to ~/Zoza_anime. Zoza internals
are never imported or modified — only job JSON files are exchanged.
"""
from app.modules.zoza_client.adapter import (
    FootballZozaAdapter,
    FakeFactoryTransport,
    HttpFactoryTransport,
)
from app.modules.zoza_client.agent import ZozaDispatcherAgent, set_session_factory
from app.modules.zoza_client.config import MAX_ATTEMPTS, factory_jobs_dir, zoza_dir
from app.modules.zoza_client.events import PUBLISHED_EVENTS, SUBSCRIBED_EVENTS, emit
from app.modules.zoza_client.factory import ZozaFactory, map_factory_state
from app.modules.zoza_client.mapper import (
    FootballProductionMapper,
    build_asset_request,
    decide_production_mode,
    map_package_to_contract,
)
from app.modules.zoza_client.package import build_zoza_package, to_zoza_job
from app.modules.zoza_client.tracker import FootballZozaTracker

def register_with_creator_os(pulse: str = "football-pulse") -> dict:
    """Fail-open Creator-OS registration. Observability only, never blocks."""
    import os
    if os.environ.get("FOOTBALLPULSE_SHARED_BUS", "0") != "1":
        try:
            import sys
            from pathlib import Path
            creator_os = Path(__file__).resolve().parents[3].parent
            if str(creator_os) not in sys.path:
                sys.path.insert(0, str(creator_os))
            from shared import orchestrator as orch  # type: ignore
            orch.register_pulse(pulse, ["sports analysis", "documentary",
                                        "REALITY_ONLY", "REALITY_FIRST", "HYBRID", "AI_CREATIVE"])
            orch.heartbeat(pulse, "healthy")
            return {"registered": pulse}
        except Exception:
            return {"registered": pulse, "shared_unavailable": True}
    try:
        import sys
        from pathlib import Path
        creator_os = Path(__file__).resolve().parents[3].parent
        if str(creator_os) not in sys.path:
            sys.path.insert(0, str(creator_os))
        from shared import orchestrator as orch  # type: ignore
        orch.register_pulse(pulse, ["sports analysis", "documentary",
                                    "REALITY_ONLY", "REALITY_FIRST", "HYBRID", "AI_CREATIVE"])
        orch.heartbeat(pulse, "healthy")
        return {"registered": pulse}
    except Exception:
        return {"registered": pulse, "shared_unavailable": True}


__all__ = [
    "MAX_ATTEMPTS",
    "PUBLISHED_EVENTS",
    "SUBSCRIBED_EVENTS",
    "FakeFactoryTransport",
    "FootballProductionMapper",
    "FootballZozaAdapter",
    "FootballZozaTracker",
    "HttpFactoryTransport",
    "ZozaDispatcherAgent",
    "ZozaFactory",
    "build_asset_request",
    "build_zoza_package",
    "decide_production_mode",
    "emit",
    "factory_jobs_dir",
    "map_factory_state",
    "map_package_to_contract",
    "register_with_creator_os",
    "set_session_factory",
    "to_zoza_job",
    "zoza_dir",
]
