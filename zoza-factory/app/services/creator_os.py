"""Creator-OS integration: event bus, orchestrator, notifications, contracts.

All calls are fail-open: shared-layer failures never break factory operation.
The factory registers as kind='factory' (never 'pulse').
"""
from __future__ import annotations

import os
import sys

FACTORY_NAME = "zoza-factory"


def _shared():
    try:
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        if root not in sys.path:
            sys.path.insert(0, root)
        from shared import event_bus  # type: ignore
        return event_bus
    except Exception:
        return None


def emit(event_type: str, payload: dict) -> None:
    bus = _shared()
    if bus is None:
        return
    try:
        bus.publish(event_type, payload, source_pulse=FACTORY_NAME)
    except Exception:
        pass


def heartbeat(queue_depth: int = 0, load: float = 0.0) -> None:
    try:
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        if root not in sys.path:
            sys.path.insert(0, root)
        from shared import orchestrator  # type: ignore
        orchestrator.register_factory(
            FACTORY_NAME,
            ["REALITY_ONLY", "REALITY_FIRST", "HYBRID", "AI_CREATIVE",
             "voice", "timeline", "render", "export"])
        orchestrator.heartbeat(FACTORY_NAME, "healthy", load, queue_depth)
    except Exception:
        pass


def notify_failure(message: str) -> None:
    try:
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        if root not in sys.path:
            sys.path.insert(0, root)
        from shared import notifications  # type: ignore
        notifications.notify("failure", message, source_pulse=FACTORY_NAME)
    except Exception:
        pass


def validate_export_against_shared(export: dict) -> dict:
    """Cross-check the export against the canonical shared contract."""
    try:
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        if root not in sys.path:
            sys.path.insert(0, root)
        from shared import contracts  # type: ignore
        return {"ok": True, "checked": bool(contracts.validate_export(dict(export)))}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}
