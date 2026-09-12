"""Pulse-owned event helpers (fail-open forwarding to shared bus).

Pulse emits: VIDEO_REQUESTED, PUBLISH_STARTED, PUBLISH_COMPLETED, REVENUE_RECORDED.
Zoza emits: VIDEO_RENDER_STARTED, VIDEO_RENDER_FINISHED, VIDEO_EXPORTED.
Names are reused from shared/event_bus, never duplicated.
"""
from __future__ import annotations

import time

PUBLISHED_EVENTS = ("VIDEO_REQUESTED", "PUBLISH_STARTED", "PUBLISH_COMPLETED", "REVENUE_RECORDED")
SUBSCRIBED_EVENTS = ("VIDEO_RENDER_STARTED", "VIDEO_RENDER_FINISHED", "VIDEO_EXPORTED")

_outbox: list[dict] = []


def emit(event_type: str, payload: dict | None = None,
         source: str = "music-pulse") -> dict:
    event = {"event_type": event_type, "source": source,
             "payload": payload or {}, "ts": time.time()}
    _outbox.append(event)
    try:
        from app.core.shared import event_bus
        event_bus.publish(event_type, payload or {}, source_pulse=source)
    except Exception:
        pass
    return event


def outbox() -> list[dict]:
    return list(_outbox)


def clear_outbox() -> None:
    _outbox.clear()
