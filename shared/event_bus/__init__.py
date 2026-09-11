"""Creator-OS cross-pulse event bus: publish/subscribe with persistence + replay.

File-backed sqlite store (shared/event_bus.db) so all pulses — including
future ones in separate processes — share one bus. In-process callbacks for
same-process subscribers; persistent poll queue for cross-process ones.
"""
from __future__ import annotations
import json
import os
import sqlite3
import threading
import time

EVENT_TYPES = ("TREND_FOUND", "CONTENT_CREATED", "PACKAGE_CREATED", "PACKAGE_SENT",
               "VIDEO_RENDERED", "VIDEO_PUBLISHED", "BREAKOUT_ARTIST", "REVENUE_EVENT",
               # Phase 8 refactor: factory render vs pulse publish split
               "VIDEO_REQUESTED", "VIDEO_RENDER_STARTED", "VIDEO_RENDER_FINISHED",
               "VIDEO_EXPORTED", "PUBLISH_STARTED", "PUBLISH_COMPLETED",
               "REVENUE_RECORDED")

_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "event_bus.db")
_lock = threading.Lock()
_callbacks: dict[str, list] = {}


def _conn():
    conn = sqlite3.connect(_DB, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
        source_pulse TEXT DEFAULT '', payload TEXT DEFAULT '{}', ts REAL DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS subscriptions (
        subscriber TEXT NOT NULL, event_type TEXT NOT NULL, last_id INTEGER DEFAULT 0,
        PRIMARY KEY (subscriber, event_type))""")
    return conn


def publish(event_type: str, payload: dict | None = None,
            source_pulse: str = "music-pulse") -> dict:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event: {event_type}")
    with _lock:
        conn = _conn()
        cur = conn.execute(
            "INSERT INTO events (event_type, source_pulse, payload, ts) VALUES (?,?,?,?)",
            (event_type, source_pulse, json.dumps(payload or {}), time.time()))
        eid = cur.lastrowid
        conn.commit()
        conn.close()
    for cb in _callbacks.get(event_type, []):
        try:
            cb({"id": eid, "event_type": event_type, "source_pulse": source_pulse,
                "payload": payload or {}})
        except Exception:
            pass
    return {"id": eid, "event_type": event_type}


def subscribe(event_type: str, callback) -> None:
    """Same-process subscription (MusicPulse uses this for Zoza callbacks)."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event: {event_type}")
    _callbacks.setdefault(event_type, []).append(callback)


def register_poller(subscriber: str, event_type: str) -> None:
    """Cross-process subscription: pulse polls pending() for new events."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event: {event_type}")
    conn = _conn()
    conn.execute("INSERT OR IGNORE INTO subscriptions (subscriber, event_type) VALUES (?,?)",
                 (subscriber, event_type))
    conn.commit()
    conn.close()


def pending(subscriber: str, event_type: str, limit: int = 50) -> list[dict]:
    conn = _conn()
    row = conn.execute("SELECT last_id FROM subscriptions WHERE subscriber=? AND event_type=?",
                       (subscriber, event_type)).fetchone()
    if row is None:
        conn.close()
        return []
    last = row[0]
    rows = conn.execute("SELECT id, event_type, source_pulse, payload FROM events "
                        "WHERE event_type=? AND id>? ORDER BY id LIMIT ?",
                        (event_type, last, limit)).fetchall()
    if rows:
        conn.execute("UPDATE subscriptions SET last_id=? WHERE subscriber=? AND event_type=?",
                     (rows[-1][0], subscriber, event_type))
        conn.commit()
    conn.close()
    return [{"id": r[0], "event_type": r[1], "source_pulse": r[2],
             "payload": json.loads(r[3] or "{}")} for r in rows]


def replay(since_id: int = 0, event_type: str | None = None, limit: int = 100) -> list[dict]:
    conn = _conn()
    if event_type:
        rows = conn.execute("SELECT id, event_type, source_pulse, payload FROM events "
                            "WHERE id>? AND event_type=? ORDER BY id LIMIT ?",
                            (since_id, event_type, limit)).fetchall()
    else:
        rows = conn.execute("SELECT id, event_type, source_pulse, payload FROM events "
                            "WHERE id>? ORDER BY id LIMIT ?",
                            (since_id, limit)).fetchall()
    conn.close()
    return [{"id": r[0], "event_type": r[1], "source_pulse": r[2],
             "payload": json.loads(r[3] or "{}")} for r in rows]


def history(limit: int = 50) -> list[dict]:
    return replay(0, limit=limit)[-limit:]
