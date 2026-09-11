"""Creator network orchestrator: health, workload, queue + resource management."""
from __future__ import annotations
import os
import sqlite3
import time

_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orchestrator.db")
STALE_AFTER_SEC = 300


def _conn():
    conn = sqlite3.connect(_DB, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS pulses (
        name TEXT PRIMARY KEY, status TEXT DEFAULT 'unknown',
        load REAL DEFAULT 0.0, queue_depth INTEGER DEFAULT 0, last_beat REAL DEFAULT 0)""")
    return conn


def heartbeat(name: str, status: str = "healthy", load: float = 0.0,
              queue_depth: int = 0) -> dict:
    conn = _conn()
    conn.execute("INSERT OR REPLACE INTO pulses (name, status, load, queue_depth, last_beat)"
                 " VALUES (?,?,?,?,?)", (name, status, load, queue_depth, time.time()))
    conn.commit()
    conn.close()
    return {"pulse": name, "status": status}


def health() -> list[dict]:
    now = time.time()
    conn = _conn()
    rows = conn.execute("SELECT name, status, load, queue_depth, last_beat FROM pulses").fetchall()
    conn.close()
    out = []
    for name, status, load, qd, beat in rows:
        state = status if (now - (beat or 0)) < STALE_AFTER_SEC else "stale"
        out.append({"pulse": name, "state": state, "load": load,
                    "queue_depth": qd, "last_beat": beat})
    return out


def distribute(work_items: list[dict]) -> dict[str, list[dict]]:
    """Assign work to the least-loaded healthy pulse first."""
    pulses = [p for p in health() if p["state"] == "healthy"] or health()
    if not pulses:
        return {"unassigned": work_items}
    pulses.sort(key=lambda p: (p["load"], p["queue_depth"]))
    plan: dict[str, list[dict]] = {p["pulse"]: [] for p in pulses}
    for i, item in enumerate(work_items):
        plan[pulses[i % len(pulses)]["pulse"]].append(item)
    return plan


def network_report() -> dict:
    pulses = health()
    return {"pulses": pulses,
            "total_queue": sum(p["queue_depth"] for p in pulses),
            "healthy": sum(1 for p in pulses if p["state"] == "healthy"),
            "network_load": round(sum(p["load"] for p in pulses), 2)}


# ---- Phase 8: pulse + factory registration, factory-aware routing ----
# Creator-OS observes and routes; it can never block pulse operation.

def register_pulse(name: str, capabilities: list | None = None) -> dict:
    conn = _conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS registry (
        name TEXT PRIMARY KEY, kind TEXT DEFAULT 'pulse',
        capabilities TEXT DEFAULT '[]', registered REAL DEFAULT 0)""")
    import json as _json
    import time as _time
    conn.execute("INSERT OR REPLACE INTO registry (name, kind, capabilities, registered)"
                 " VALUES (?,?,?,?)",
                 (name, "pulse", _json.dumps(capabilities or []), _time.time()))
    conn.commit()
    conn.close()
    heartbeat(name, "healthy")
    return {"registered": name, "kind": "pulse"}


def register_factory(name: str, capabilities: list | None = None) -> dict:
    import json as _json
    import time as _time
    conn = _conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS registry (
        name TEXT PRIMARY KEY, kind TEXT DEFAULT 'pulse',
        capabilities TEXT DEFAULT '[]', registered REAL DEFAULT 0)""")
    conn.execute("INSERT OR REPLACE INTO registry (name, kind, capabilities, registered)"
                 " VALUES (?,?,?,?)",
                 (name, "factory", _json.dumps(capabilities or []), _time.time()))
    conn.commit()
    conn.close()
    heartbeat(name, "healthy")
    return {"registered": name, "kind": "factory"}


def list_registered(kind: str | None = None) -> list[dict]:
    import json as _json
    conn = _conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS registry (
        name TEXT PRIMARY KEY, kind TEXT DEFAULT 'pulse',
        capabilities TEXT DEFAULT '[]', registered REAL DEFAULT 0)""")
    rows = conn.execute("SELECT name, kind, capabilities FROM registry").fetchall()
    conn.close()
    out = [{"name": r[0], "kind": r[1], "capabilities": _json.loads(r[2] or "[]")}
           for r in rows]
    return [o for o in out if kind is None or o["kind"] == kind]


def route_to_factory(work_items: list[dict]) -> dict[str, list[dict]]:
    """Render work always routes to a registered factory; publish work never does."""
    factories = [p for p in health()
                 if p["pulse"] in {r["name"] for r in list_registered("factory")}
                 and p["state"] == "healthy"]
    if not factories:
        return {"unassigned": work_items}
    factories.sort(key=lambda p: (p["load"], p["queue_depth"]))
    plan: dict[str, list[dict]] = {f["pulse"]: [] for f in factories}
    for i, item in enumerate(work_items):
        plan[factories[i % len(factories)]["pulse"]].append(item)
    return plan
