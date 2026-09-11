"""Creator-OS Notification Center: all pulses report here.

Channels: log (always), webhook, email (logged stub), telegram (fail-open).
Store: shared/notifications.db. Nothing here is a runtime dependency of pulses.
"""
from __future__ import annotations
import json
import logging
import os
import sqlite3
import time

log = logging.getLogger("creator-notifications")

CHANNELS = ("log", "webhook", "email", "telegram")
EVENTS = ("revenue", "system", "failure", "opportunity", "deployment")

_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notifications.db")


def _conn():
    conn = sqlite3.connect(_DB, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS notification_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL,
        source_pulse TEXT DEFAULT '', message TEXT DEFAULT '', ts REAL DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS notification_channels (
        channel TEXT PRIMARY KEY, config TEXT DEFAULT '{}', enabled INTEGER DEFAULT 1)""")
    return conn


def configure(channel: str, config: dict | None = None, enabled: bool = True) -> dict:
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel: {channel}")
    conn = _conn()
    conn.execute("INSERT OR REPLACE INTO notification_channels (channel, config, enabled)"
                 " VALUES (?,?,?)", (channel, json.dumps(config or {}), int(enabled)))
    conn.commit()
    conn.close()
    return {"channel": channel, "enabled": enabled}


def _enabled(channel: str) -> tuple[bool, dict]:
    conn = _conn()
    row = conn.execute("SELECT config, enabled FROM notification_channels WHERE channel=?",
                       (channel,)).fetchone()
    conn.close()
    if row is None:
        return (channel == "log"), {}
    return bool(row[1]), json.loads(row[0] or "{}")


def notify(event: str, message: str, source_pulse: str = "music-pulse") -> dict:
    """Persist + fan out. Never raises — notifications must not break pulses."""
    if event not in EVENTS:
        raise ValueError(f"unknown event: {event}")
    conn = _conn()
    cur = conn.execute("INSERT INTO notification_events (event, source_pulse, message, ts)"
                       " VALUES (?,?,?,?)", (event, source_pulse, message, time.time()))
    nid = cur.lastrowid
    conn.commit()
    conn.close()
    delivered: dict[str, str] = {}
    for channel in CHANNELS:
        try:
            enabled, cfg = _enabled(channel)
            if enabled:
                _send(channel, event, message, cfg)
                delivered[channel] = "sent"
        except Exception as exc:
            delivered[channel] = f"failed: {exc}"
    try:
        from shared import event_bus
        event_bus.publish("REVENUE_EVENT" if event == "revenue" else "VIDEO_PUBLISHED",
                          {"notification_id": nid, "message": message},
                          source_pulse=source_pulse)
    except Exception:
        pass
    return {"id": nid, "delivered": delivered}


def _send(channel: str, event: str, message: str, cfg: dict) -> None:
    text = f"[{event}] {message}"
    if channel == "log":
        log.warning(text)
    elif channel == "webhook":
        url = cfg.get("url") or os.environ.get("CREATOR_WEBHOOK_URL", "")
        if not url:
            return
        import httpx
        httpx.post(url, json={"event": event, "message": message}, timeout=10)
    elif channel == "email":
        log.warning("EMAIL(to=%s): %s", cfg.get("to", "ops"), text)
    elif channel == "telegram":
        token = cfg.get("token") or os.environ.get("CREATOR_TELEGRAM_TOKEN", "")
        chat = cfg.get("chat_id") or os.environ.get("CREATOR_TELEGRAM_CHAT", "")
        if not token or not chat:
            return
        import httpx
        httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                   json={"chat_id": chat, "text": text[:4000]}, timeout=15)


def recent(limit: int = 50, event: str | None = None) -> list[dict]:
    conn = _conn()
    if event:
        rows = conn.execute("SELECT id, event, source_pulse, message, ts FROM notification_events "
                            "WHERE event=? ORDER BY id DESC LIMIT ?", (event, limit)).fetchall()
    else:
        rows = conn.execute("SELECT id, event, source_pulse, message, ts FROM notification_events "
                            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [{"id": r[0], "event": r[1], "source": r[2], "message": r[3]} for r in rows]
