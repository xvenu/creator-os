"""Event integration: pulse-owned outbox + fail-open shared bus forwarding.

Published (pulse → factory/network): VIDEO_REQUESTED, PUBLISH_STARTED,
PUBLISH_COMPLETED, REVENUE_RECORDED.
Subscribed (factory → pulse): VIDEO_RENDER_STARTED, VIDEO_RENDER_FINISHED,
VIDEO_EXPORTED.

Local outbox is authoritative for tests and audits. Forwarding to the
Creator-OS shared bus is best-effort: shared-layer failures never raise
(fail-open, per pulse contract).
"""
from __future__ import annotations

import time

from app.core.logging import get_logger

log = get_logger("zoza.events")

PUBLISHED_EVENTS = ("VIDEO_REQUESTED", "PUBLISH_STARTED", "PUBLISH_COMPLETED", "REVENUE_RECORDED")
SUBSCRIBED_EVENTS = ("VIDEO_RENDER_STARTED", "VIDEO_RENDER_FINISHED", "VIDEO_EXPORTED")

_outbox: list[dict] = []
_subscribers: dict[str, list] = {}


def emit(event_type: str, payload: dict | None = None, source: str = "football-pulse") -> dict:
    event = {"event_type": event_type, "source": source,
             "payload": payload or {}, "ts": time.time()}
    _outbox.append(event)
    log.info("event_emitted", event_type=event_type, source=source)
    for callback in _subscribers.get(event_type, []):
        try:
            callback(event)
        except Exception:  # noqa: BLE001 — subscriber faults never break emission
            pass
    _forward_to_shared_bus(event)
    return event


def subscribe(event_type: str, callback) -> None:
    _subscribers.setdefault(event_type, []).append(callback)


def outbox() -> list[dict]:
    return list(_outbox)


def clear_outbox() -> None:
    _outbox.clear()


def _forward_to_shared_bus(event: dict) -> None:
    import os

    if os.environ.get("FOOTBALLPULSE_SHARED_BUS", "0") != "1":
        return  # opt-in: tests and offline runs stay local-only
    try:
        import sys
        from pathlib import Path

        creator_os = Path(__file__).resolve().parents[3].parent  # football-pulse/..
        if str(creator_os) not in sys.path:
            sys.path.insert(0, str(creator_os))
        from shared.event_bus import publish as shared_publish  # type: ignore
        shared_publish(event["event_type"], event["payload"], source_pulse=event["source"])
    except Exception as exc:  # noqa: BLE001 — fail open by contract
        log.info("shared_bus_forward_skipped", reason=str(exc)[:120])
