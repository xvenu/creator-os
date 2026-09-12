"""Local factory-status tracking (Pulse-owned, never blocks autonomy)."""
from __future__ import annotations

import time

TERMINAL_STATES = ("exported", "failed")
TRACKED_STATES = ("created", "planned", "acquiring", "assembling",
                  "rendering", "exported", "failed")


class MusicZozaTracker:
    """Idempotent local record: content_key -> request_id.

    Fields per spec: request_id, local package ID, factory state,
    submitted_at, updated_at, retry count, export availability,
    failure reason.
    """

    def __init__(self) -> None:
        self._by_request: dict[str, dict] = {}
        self._by_content: dict[str, str] = {}

    def create_or_get(self, content_key: str, request_id: str,
                      local_package_id: str, payload: dict) -> tuple[dict, bool]:
        existing_id = self._by_content.get(content_key)
        if existing_id and existing_id in self._by_request:
            rec = self._by_request[existing_id]
            # Same production requirements -> same request_id: reuse.
            if rec["request_id"] == request_id:
                return rec, True
        if request_id in self._by_request:
            return self._by_request[request_id], True
        now = time.time()
        rec = {
            "request_id": request_id,
            "local_package_id": local_package_id,
            "content_key": content_key,
            "factory_state": "created",
            "submitted_at": now,
            "updated_at": now,
            "retry_count": 0,
            "export": None,
            "export_available": False,
            "failure_reason": "",
            "payload": dict(payload),
        }
        self._by_request[request_id] = rec
        self._by_content[content_key] = request_id
        return rec, False

    def get(self, request_id: str) -> dict | None:
        return self._by_request.get(request_id)

    def get_by_content(self, content_key: str) -> dict | None:
        rid = self._by_content.get(content_key)
        return self._by_request.get(rid) if rid else None

    def update_state(self, request_id: str, state: str,
                     failure_reason: str = "") -> dict:
        rec = self._by_request.get(request_id)
        if rec is None:
            raise ValueError(f"unknown request: {request_id}")
        if state not in TRACKED_STATES:
            raise ValueError(f"unknown factory state: {state}")
        rec["factory_state"] = state
        rec["updated_at"] = time.time()
        if failure_reason:
            rec["failure_reason"] = failure_reason
        elif state != "failed":
            rec["failure_reason"] = ""
        return rec

    def record_retry(self, request_id: str) -> dict:
        rec = self._by_request.get(request_id)
        if rec is None:
            raise ValueError(f"unknown request: {request_id}")
        rec["retry_count"] += 1
        rec["updated_at"] = time.time()
        return rec

    def record_export(self, request_id: str, export: dict) -> dict:
        rec = self._by_request.get(request_id)
        if rec is None:
            raise ValueError(f"unknown request: {request_id}")
        rec["export"] = dict(export)
        rec["export_available"] = True
        rec["factory_state"] = "exported"
        rec["updated_at"] = time.time()
        rec["failure_reason"] = ""
        return rec

    def all(self) -> list[dict]:
        return list(self._by_request.values())
