"""Zoza client: FootballPulse → Zoza Video Factory bridge.

FootballPulse owns intelligence → packages → publishing → revenue.
It never renders. This module submits packages to the factory, tracks
factory jobs, collects contract-validated exports, and retries failures.

Factory addressing mirrors the Creator-OS convention (same as music-pulse):
$ZOZA_DIR/jobs/*.json file queue, defaulting to ~/Zoza_anime. Zoza internals
are never imported or modified — only job JSON files are exchanged.
"""
from app.modules.zoza_client.agent import ZozaDispatcherAgent, set_session_factory
from app.modules.zoza_client.config import MAX_ATTEMPTS, factory_jobs_dir, zoza_dir
from app.modules.zoza_client.events import PUBLISHED_EVENTS, SUBSCRIBED_EVENTS, emit
from app.modules.zoza_client.factory import ZozaFactory, map_factory_state
from app.modules.zoza_client.package import build_zoza_package, to_zoza_job

__all__ = [
    "MAX_ATTEMPTS",
    "PUBLISHED_EVENTS",
    "SUBSCRIBED_EVENTS",
    "ZozaDispatcherAgent",
    "ZozaFactory",
    "build_zoza_package",
    "emit",
    "factory_jobs_dir",
    "map_factory_state",
    "set_session_factory",
    "to_zoza_job",
    "zoza_dir",
]
