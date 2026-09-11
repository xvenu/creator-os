"""Multi-Brand Orchestrator: coordinate brands/regions, prevent conflicts."""
from __future__ import annotations

from app.core.audit import audit


def detect_overlap(db) -> list[dict]:
    """Nodes sharing a parent + region compete for the same audience."""
    from app.modules.network.engine import nodes
    all_nodes = nodes(db)
    seen: dict[tuple[str, str], list[str]] = {}
    for n in all_nodes:
        seen.setdefault((n["parent"], n["region"]), []).append(n["name"])
    return [{"parent": p or "root", "region": r, "nodes": names}
            for (p, r), names in seen.items() if len(names) > 1]


def detect_duplication(topics_by_node: dict[str, list[str]]) -> list[dict]:
    """Same topic scheduled on multiple nodes = duplication waste."""
    inv: dict[str, list[str]] = {}
    for node, topics in topics_by_node.items():
        for t in topics:
            inv.setdefault(t.lower(), []).append(node)
    return [{"topic": t, "nodes": ns} for t, ns in inv.items() if len(ns) > 1]


def resolve_conflicts(db, actor: str = "orchestrator") -> list[dict]:
    overlaps = detect_overlap(db)
    resolutions = [{"conflict": f"{o['parent']}/{o['region']}",
                    "resolution": f"stagger {o['nodes']} by genre focus; "
                                  "eldest node keeps breaking news"} for o in overlaps]
    audit(db, actor, "orchestrator.resolved", "network", "",
          {"count": len(resolutions)})
    return resolutions


def network_plan(db, actor: str = "orchestrator") -> dict:
    from app.modules.network.engine import allocate_resources
    alloc = allocate_resources(db, actor)
    return {"allocation": alloc, "overlaps": detect_overlap(db),
            "resolutions": resolve_conflicts(db, actor),
            "objective": "maximize network-wide growth + revenue, zero duplication"}
