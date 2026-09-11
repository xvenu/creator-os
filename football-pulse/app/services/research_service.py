"""ResearchService: aggregate intelligence into structured research briefs.

Deterministic aggregation over intel items (news / transfers / predictions /
match analyses / opportunities). No external fetching in Phase 4 — inputs
arrive as structured payloads; the service enriches, orders and scores them.
"""
from __future__ import annotations

import datetime as dt


def aggregate_facts(items: list[dict]) -> list[dict]:
    """Dedupe facts by normalized text, keeping highest-confidence version."""
    seen: dict[str, dict] = {}
    for item in items:
        for fact in item.get("facts", []) or []:
            text = " ".join(str(fact.get("text", "")).split())
            if not text:
                continue
            key = text.lower()
            conf = float(fact.get("confidence", 0.5))
            if key not in seen or conf > float(seen[key].get("confidence", 0)):
                seen[key] = {"text": text, "confidence": conf,
                             "source": fact.get("source", item.get("source_kind", "unknown"))}
    return sorted(seen.values(), key=lambda f: f["confidence"], reverse=True)


def enrich_entities(items: list[dict]) -> dict:
    """Merge entity dicts across items → {clubs, competitions, people} ranked by mentions."""
    counts: dict[str, dict[str, int]] = {"clubs": {}, "competitions": {}, "people": {}}
    for item in items:
        entities = item.get("entities", {}) or {}
        for kind in counts:
            for e in entities.get(kind, []) or []:
                key = str(e).strip()
                if key:
                    counts[kind][key] = counts[kind].get(key, 0) + 1
    return {
        kind: sorted(names, key=lambda n: counts[kind][n], reverse=True)
        for kind, names in counts.items()
    }


def build_timeline(items: list[dict]) -> list[dict]:
    """Chronological event list from dated items + rumor/score milestones."""
    events: list[dict] = []
    for item in items:
        ts = item.get("published_at") or item.get("last_updated") or item.get("generated_at")
        events.append({
            "at": str(ts) if ts else None,
            "event": str(item.get("title", item.get("topic", "update"))),
            "source_kind": item.get("source_kind", "unknown"),
        })
    dated = [e for e in events if e["at"]]
    undated = [e for e in events if not e["at"]]
    return sorted(dated, key=lambda e: e["at"]) + undated


def extract_narrative(items: list[dict], entities: dict) -> tuple[list[str], float]:
    """Supporting points + confidence from fact/entity density and source spread."""
    facts = aggregate_facts(items)
    points = [f["text"] for f in facts[:5]]
    clubs = entities.get("clubs", [])
    if clubs:
        points.append(f"Key angle: {clubs[0]} drive the narrative.")
    sources = {str(i.get("source_kind", "")) for i in items}
    confidence = round(min(0.4 + 0.1 * len(facts) + 0.08 * len(sources), 0.95), 3)
    return points, confidence


def expand_topic(topic: str, entities: dict) -> list[str]:
    """Related sub-topic suggestions from entity presence."""
    expansions = [topic]
    for club in (entities.get("clubs", []) or [])[:3]:
        expansions.append(f"{club}: latest developments")
    for comp in (entities.get("competitions", []) or [])[:2]:
        expansions.append(f"{comp} implications")
    return expansions


def build_brief(topic: str, items: list[dict]) -> dict:
    """Full research brief → {topic, facts, entities, timeline, ...}."""
    entities = enrich_entities(items)
    points, confidence = extract_narrative(items, entities)
    references = [
        {"title": str(i.get("title", "")), "source_kind": i.get("source_kind", "unknown")}
        for i in items if i.get("title")
    ]
    return {
        "topic": topic,
        "facts": aggregate_facts(items),
        "entities": entities,
        "timeline": build_timeline(items),
        "supporting_points": points,
        "confidence": confidence,
        "references": references,
        "expanded_topics": expand_topic(topic, entities),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
