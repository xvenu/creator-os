"""Network Expansion Engine: multi-brand / multi-region network management."""
from __future__ import annotations

from app.core.audit import audit

KINDS = ("website", "brand", "account", "region", "network")
DEFAULT_NODES = [
    ("MusicPulse Global", "network", "", "US"),
    ("MusicPulse US", "region", "MusicPulse Global", "US"),
    ("MusicPulse UK", "region", "MusicPulse Global", "UK"),
    ("MusicPulse Hip-Hop", "brand", "MusicPulse Global", "US"),
    ("MusicPulse Pop", "brand", "MusicPulse Global", "US"),
    ("MusicPulse EDM", "brand", "MusicPulse Global", "DE"),
    ("MusicPulse Country", "brand", "MusicPulse US", "US"),
]


def register_node(db, name: str, kind: str, parent: str = "",
                  region: str = "US", actor: str = "network"):
    from app.models.phase4 import NetworkNode
    if kind not in KINDS:
        raise ValueError(f"kind must be {KINDS}")
    row = NetworkNode(name=name, kind=kind, parent=parent, region=region.upper())
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "network.registered", "network", row.id, {"name": name})
    return row


def seed_default_network(db, actor: str = "network") -> int:
    from app.models.phase4 import NetworkNode
    existing = {r.name for r in db.query(NetworkNode).all()}
    n = 0
    for name, kind, parent, region in DEFAULT_NODES:
        if name not in existing:
            db.add(NetworkNode(name=name, kind=kind, parent=parent, region=region))
            n += 1
    db.commit()
    audit(db, actor, "network.seeded", "network", "", {"added": n})
    return n


def nodes(db, kind: str | None = None) -> list[dict]:
    from app.models.phase4 import NetworkNode
    q = db.query(NetworkNode).order_by(NetworkNode.id)
    if kind:
        q = q.filter(NetworkNode.kind == kind)
    return [{"id": r.id, "name": r.name, "kind": r.kind,
             "parent": r.parent, "region": r.region, "active": r.active}
            for r in q.all()]


def allocate_resources(db, actor: str = "executive") -> dict:
    """Executive resource/content/growth allocation across nodes by opportunity."""
    from app.modules.allocation.engine import priority_queue
    opps = priority_queue(db, 10)
    node_list = nodes(db) or [{"name": "MusicPulse Global"}]
    per_node = max(1, len(opps) // max(len(node_list), 1))
    plan = {n["name"] if isinstance(n, dict) else n: [] for n in node_list}
    names = list(plan)
    for i, opp in enumerate(opps):
        plan[names[i % len(names)]].append(opp["key"])
    audit(db, actor, "network.allocated", "network", "", {"nodes": len(plan)})
    return {"resource_allocation": plan, "per_node": per_node,
            "growth_allocation": {k: len(v) for k, v in plan.items()}}
