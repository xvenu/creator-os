"""Shared publishing contract: Zoza exports, Pulse publishes.

Zoza (factory) output — render-only, never published::

    {"job_id": ..., "status": "rendered", "video_path": ...,
     "thumbnail_path": ..., "metadata": {...}}

Pulse-side publishable asset::

    {"asset_id": ..., "video": ..., "thumbnail": ..., "title": ...,
     "description": ..., "hashtags": [...], "metadata": {...}}
"""
from __future__ import annotations


def validate_export(payload: dict) -> dict:
    required = ("job_id", "status", "video_path", "thumbnail_path", "metadata")
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(f"export missing fields: {missing}")
    if payload["status"] != "rendered":
        raise ValueError("export status must be 'rendered' (factory never publishes)")
    if not isinstance(payload["metadata"], dict):
        raise ValueError("export metadata must be an object")
    return payload


def validate_asset(payload: dict) -> dict:
    required = ("asset_id", "video", "thumbnail", "title", "description",
                "hashtags", "metadata")
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(f"asset missing fields: {missing}")
    if not isinstance(payload["hashtags"], list):
        raise ValueError("asset hashtags must be a list")
    return payload


def asset_from_export(export: dict, title: str = "", description: str = "",
                      hashtags: list | None = None) -> dict:
    validate_export(export)
    meta = dict(export.get("metadata") or {})
    return validate_asset({
        "asset_id": f"asset-{export['job_id']}",
        "video": export["video_path"],
        "thumbnail": export["thumbnail_path"],
        "title": title or meta.get("title", export["job_id"]),
        "description": description or meta.get("description", ""),
        "hashtags": hashtags if hashtags is not None else meta.get("hashtags", []),
        "metadata": {**meta, "zoza_job": export["job_id"]},
    })
