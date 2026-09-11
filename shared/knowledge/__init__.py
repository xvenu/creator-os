"""Creator-OS shared knowledge layer: artist/genre/trend/market/video knowledge.

File-backed sqlite (shared/knowledge.db), accessible by every pulse.
MusicPulse mirrors writes into its SharedKnowledge table for audit/API.
"""
from __future__ import annotations
import json
import os
import sqlite3
import time

DOMAINS = ("artist", "genre", "trend", "market", "video")
_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge.db")


def _conn():
    conn = sqlite3.connect(_DB, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS knowledge (
        domain TEXT NOT NULL, key TEXT NOT NULL, value TEXT DEFAULT '{}',
        source_pulse TEXT DEFAULT '', updated REAL DEFAULT 0,
        PRIMARY KEY (domain, key))""")
    return conn


def put(domain: str, key: str, value: dict, source_pulse: str = "music-pulse") -> dict:
    if domain not in DOMAINS:
        raise ValueError(f"unknown domain: {domain}")
    conn = _conn()
    conn.execute("INSERT OR REPLACE INTO knowledge (domain, key, value, source_pulse, updated)"
                 " VALUES (?,?,?,?,?)",
                 (domain, key, json.dumps(value), source_pulse, time.time()))
    conn.commit()
    conn.close()
    return {"domain": domain, "key": key}


def get(domain: str, key: str) -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT value, source_pulse FROM knowledge WHERE domain=? AND key=?",
                       (domain, key)).fetchone()
    conn.close()
    if not row:
        return None
    return {"value": json.loads(row[0] or "{}"), "source_pulse": row[1]}


def search(domain: str, query: str = "", limit: int = 20) -> list[dict]:
    conn = _conn()
    if query:
        rows = conn.execute("SELECT key, value, source_pulse FROM knowledge "
                            "WHERE domain=? AND key LIKE ? LIMIT ?",
                            (domain, f"%{query}%", limit)).fetchall()
    else:
        rows = conn.execute("SELECT key, value, source_pulse FROM knowledge "
                            "WHERE domain=? LIMIT ?", (domain, limit)).fetchall()
    conn.close()
    return [{"key": r[0], "value": json.loads(r[1] or "{}"), "source": r[2]} for r in rows]
