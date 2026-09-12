"""Thin adapter: Pulse decision -> Contract V2 -> factory -> export.

Idempotent: same content key + same production requirements reuse the same
request_id and never create duplicate jobs. Factory-unavailable never raises
into the autonomy loop — the request stays retryable.
"""
from __future__ import annotations

import os
from typing import Any

from app.modules.zoza_client import events
from app.modules.zoza_client.mapper import (
    map_package_to_contract,
    validate_against_canonical,
)
from app.modules.zoza_client.tracker import MusicZozaTracker

MAX_ATTEMPTS = 5


class FakeFactoryTransport:
    """In-memory factory double for tests (mimics REQUEST_STATES)."""

    def __init__(self, fail_submit: bool = False, unreachable: bool = False) -> None:
        self.requests: dict[str, dict] = {}
        self.fail_submit = fail_submit
        self.unreachable = unreachable

    def ping(self) -> dict:
        return {"reachable": not self.unreachable}

    def submit(self, payload: dict) -> dict:
        if self.unreachable:
            return {"ok": False, "error": "factory-unreachable", "retryable": True}
        if self.fail_submit:
            return {"ok": False, "error": "factory rejected", "retryable": True}
        rid = payload["request_id"]
        if rid in self.requests:
            return {"ok": True, "request_id": rid, "state": self.requests[rid]["state"],
                    "reused": True}
        self.requests[rid] = {"payload": dict(payload), "state": "created"}
        return {"ok": True, "request_id": rid, "state": "created", "reused": False}

    def set_state(self, request_id: str, state: str) -> None:
        self.requests[request_id]["state"] = state

    def status(self, request_id: str) -> dict:
        if self.unreachable:
            return {"ok": False, "error": "factory-unreachable", "retryable": True}
        row = self.requests.get(request_id)
        if row is None:
            return {"ok": False, "error": "not-found", "retryable": False}
        return {"ok": True, "request_id": request_id, "state": row["state"]}

    def export(self, request_id: str) -> dict:
        row = self.requests.get(request_id)
        if row is None:
            return {"ok": False, "error": "not-found"}
        if row["state"] != "exported":
            return {"ok": False, "error": f"not exported (state={row['state']})"}
        payload = row["payload"]
        export = {
            "job_id": request_id,
            "status": "rendered",
            "video_path": f"/exports/{request_id}/video.mp4",
            "thumbnail_path": f"/exports/{request_id}/thumbnail.jpg",
            "metadata": {
                "title": payload.get("goal", ""),
                "production_mode": payload.get("production_mode", ""),
                "voice_profile": payload.get("voice_profile", ""),
            },
        }
        return {"ok": True, "export": export}


class HttpFactoryTransport:
    """Production transport: zoza-factory HTTP API (fail-open)."""

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self.base_url = (base_url or os.environ.get("ZOZA_FACTORY_URL", "")).rstrip("/")
        self.timeout = timeout

    def ping(self) -> dict:
        if not self.base_url:
            return {"reachable": False, "reason": "ZOZA_FACTORY_URL not set"}
        try:
            import httpx
            r = httpx.get(f"{self.base_url}/health/live", timeout=self.timeout)
            return {"reachable": r.status_code == 200}
        except Exception as exc:
            return {"reachable": False, "reason": str(exc)[:150]}

    def submit(self, payload: dict) -> dict:
        if not self.base_url:
            return {"ok": False, "error": "factory-unreachable", "retryable": True}
        try:
            import httpx
            r = httpx.post(f"{self.base_url}/requests", json=payload, timeout=self.timeout)
            if r.status_code == 409:
                return {"ok": True, "request_id": payload["request_id"],
                        "state": "created", "reused": True}
            r.raise_for_status()
            data = r.json()
            return {"ok": True, "request_id": data.get("request_id", payload["request_id"]),
                    "state": data.get("state", "created"), "reused": False}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200], "retryable": True}

    def status(self, request_id: str) -> dict:
        try:
            import httpx
            r = httpx.get(f"{self.base_url}/requests/{request_id}", timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            return {"ok": True, "request_id": request_id, "state": data.get("state", "created")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200], "retryable": True}

    def export(self, request_id: str) -> dict:
        try:
            import httpx
            r = httpx.get(f"{self.base_url}/exports/{request_id}", timeout=self.timeout)
            if r.status_code != 200:
                return {"ok": False, "error": f"not exported ({r.status_code})"}
            return {"ok": True, "export": r.json()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200]}


def _validate_export_shape(export: dict) -> dict:
    try:
        from app.core.shared import contracts
        contracts.validate_export(dict(export))
        return export
    except ImportError:
        pass
    except Exception as exc:
        raise ValueError(str(exc)) from exc
    required = ("job_id", "status", "video_path", "thumbnail_path", "metadata")
    missing = [k for k in required if k not in export]
    if missing:
        raise ValueError(f"export missing fields: {missing}")
    if export["status"] != "rendered":
        raise ValueError("export status must be 'rendered' (factory never publishes)")
    return export


class MusicZozaAdapter:
    """Caller-side adapter (spec name). No rendering, no publishing inside."""

    def __init__(self, transport: Any | None = None,
                 tracker: MusicZozaTracker | None = None,
                 max_attempts: int = MAX_ATTEMPTS) -> None:
        self.transport = transport or HttpFactoryTransport()
        self.tracker = tracker or MusicZozaTracker()
        self.max_attempts = max_attempts

    def _content_key(self, package: dict, contract: dict) -> str:
        pid = str(package.get("id", package.get("package_id")))
        return f"{pid}:{contract['request_id']}"

    def submit_package(self, package: dict, **overrides) -> dict:
        contract = map_package_to_contract(package, **overrides)
        validate_against_canonical(contract)
        local_id = str(package.get("id", package.get("package_id")))
        content_key = self._content_key(package, contract)
        rec, reused = self.tracker.create_or_get(content_key, contract["request_id"],
                                                 local_id, contract)
        if reused and rec.get("factory_state") not in ("", "created", None):
            return {"request_id": rec["request_id"], "state": rec["factory_state"],
                    "reused": True, "submitted": True}
        if reused and rec.get("submitted_once"):
            return {"request_id": rec["request_id"], "state": rec["factory_state"],
                    "reused": True, "submitted": True}
        ping = self.transport.ping() if hasattr(self.transport, "ping") else {"reachable": True}
        if not ping.get("reachable", True):
            events.emit("VIDEO_REQUESTED", {"package_id": local_id,
                                            "request_id": rec["request_id"],
                                            "state": "created", "reason": "factory-unreachable"})
            return {"request_id": rec["request_id"], "state": "created",
                    "submitted": False, "reason": "factory-unreachable", "retryable": True}
        result = self.transport.submit(contract)
        if not result.get("ok"):
            self.tracker.update_state(rec["request_id"], "created",
                                      failure_reason=str(result.get("error", "")))
            events.emit("VIDEO_REQUESTED", {"package_id": local_id,
                                            "request_id": rec["request_id"],
                                            "state": "created",
                                            "error": str(result.get("error", ""))})
            return {"request_id": rec["request_id"], "state": "created",
                    "submitted": False, "error": result.get("error"),
                    "retryable": bool(result.get("retryable", True))}
        rec["submitted_once"] = True
        self.tracker.update_state(rec["request_id"], "created")
        events.emit("VIDEO_REQUESTED", {"package_id": local_id,
                                        "request_id": rec["request_id"], "state": "created"})
        return {"request_id": rec["request_id"], "state": "created",
                "submitted": True, "reused": bool(result.get("reused", reused))}

    def poll(self, request_id: str) -> dict:
        rec = self.tracker.get(request_id)
        if rec is None:
            raise ValueError(f"unknown request: {request_id}")
        if rec["factory_state"] in ("exported", "failed"):
            return {"request_id": request_id, "state": rec["factory_state"], "terminal": True}
        result = self.transport.status(request_id)
        if not result.get("ok"):
            if result.get("retryable", True):
                return {"request_id": request_id, "state": rec["factory_state"],
                        "factory_unreachable": True, "retryable": True}
            self.tracker.update_state(request_id, "failed",
                                      failure_reason=str(result.get("error", "")))
            return {"request_id": request_id, "state": "failed",
                    "error": result.get("error")}
        state = str(result.get("state", "created"))
        self.tracker.update_state(request_id, state)
        out: dict[str, Any] = {"request_id": request_id, "state": state}
        if state == "failed":
            out["retryable"] = True
        if state in ("exported",):
            out["terminal"] = True
        return out

    def retry(self, request_id: str) -> dict:
        rec = self.tracker.get(request_id)
        if rec is None:
            raise ValueError(f"unknown request: {request_id}")
        if rec["factory_state"] == "exported":
            return {"request_id": request_id, "state": "exported", "terminal": True}
        if rec["retry_count"] >= self.max_attempts:
            if rec["factory_state"] != "failed":
                self.tracker.update_state(request_id, "failed",
                                          failure_reason="retries exhausted")
            return {"request_id": request_id, "state": "failed", "terminal": True}
        self.tracker.record_retry(request_id)
        ping = self.transport.ping() if hasattr(self.transport, "ping") else {"reachable": True}
        if not ping.get("reachable", True):
            return {"request_id": request_id, "state": rec["factory_state"],
                    "retried": False, "reason": "factory-unreachable", "retryable": True}
        # Idempotent re-submit of the original contract payload.
        result = self.transport.submit(dict(rec.get("payload", {})))
        if not result.get("ok") and not result.get("reused"):
            return {"request_id": request_id, "state": rec["factory_state"],
                    "retried": False, "error": result.get("error"), "retryable": True}
        return self.poll(request_id)

    def consume_export(self, request_id: str) -> dict:
        rec = self.tracker.get(request_id)
        if rec is None:
            raise ValueError(f"unknown request: {request_id}")
        result = self.transport.export(request_id)
        if not result.get("ok"):
            return {"ok": False, "request_id": request_id, "error": result.get("error")}
        export = _validate_export_shape(dict(result["export"]))
        self.tracker.record_export(request_id, export)
        return {"ok": True, "request_id": request_id, "export": export}
