"""Creator-OS knowledge graphs: artist / label / event / release / source.

Edge store alongside the key-value knowledge.db. Every pulse reads/writes
the same graphs; music-pulse mirrors nothing (graphs are shared-native).
"""
from __future__ import annotations
import os
import sqlite3
import time

GRAPH_DOMAINS = ("artist_graph", "label_graph", "event_graph",
                 "release_graph", "source_graph")
_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge.db")


def _conn():
    conn = sqlite3.connect(_DB, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS graph_edges (
        domain TEXT NOT NULL, src TEXT NOT NULL, rel TEXT NOT NULL, dst TEXT NOT NULL,
        source_pulse TEXT DEFAULT '', updated REAL DEFAULT 0,
        PRIMARY KEY (domain, src, rel, dst))""")
    return conn


def link(domain: str, src: str, rel: str, dst: str,
         source_pulse: str = "music-pulse") -> dict:
    if domain not in GRAPH_DOMAINS:
        raise ValueError(f"unknown graph: {domain}")
    conn = _conn()
    conn.execute("INSERT OR REPLACE INTO graph_edges (domain, src, rel, dst, source_pulse, updated)"
                 " VALUES (?,?,?,?,?,?)", (domain, src, rel, dst, source_pulse, time.time()))
    conn.commit()
    conn.close()
    return {"domain": domain, "src": src, "rel": rel, "dst": dst}


def neighbors(domain: str, node: str, limit: int = 20) -> list[dict]:
    conn = _conn()
    rows = conn.execute("SELECT src, rel, dst, source_pulse FROM graph_edges "
                        "WHERE domain=? AND (src=? OR dst=?) LIMIT ?",
                        (domain, node, node, limit)).fetchall()
    conn.close()
    return [{"src": r[0], "rel": r[1], "dst": r[2], "source": r[3]} for r in rows]


def graph_stats() -> dict:
    conn = _conn()
    rows = conn.execute("SELECT domain, COUNT(*) FROM graph_edges GROUP BY domain").fetchall()
    conn.close()
    return {d: n for d, n in rows}
