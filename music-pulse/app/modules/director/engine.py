"""Autonomous Content Director: what gets produced, how much, in what format."""
from __future__ import annotations

from app.core.audit import audit


def build_directives(db, max_items: int = 5, actor: str = "director") -> list[dict]:
    """Turn strategy + opportunity scores into publishing directives."""
    from app.modules.executive.engine import latest_strategy
    from app.modules.allocation.engine import priority_queue
    strategy = latest_strategy(db) or {"genres": ["Pop"], "artists": [], "markets": ["US"]}
    opps = priority_queue(db, max_items * 2)
    directives = []
    for i, opp in enumerate(opps[:max_items]):
        key = opp["key"]
        if key.startswith("song:"):
            kind, topic = "short", key[5:]
        elif key.startswith("artist:"):
            kind, topic = "profile", key[7:]
        elif key.startswith("genre:"):
            kind, topic = "ranking", key[6:]
        else:
            kind, topic = "news", key.split(":", 1)[-1]
        genre = (strategy.get("genres") or ["Pop"])[i % len(strategy.get("genres") or ["Pop"])]
        directives.append({"kind": kind, "topic": topic, "genre": genre,
                           "artist": "", "priority": max_items - i,
                           "market": (strategy.get("markets") or ["US"])[0]})
    audit(db, actor, "director.planned", "directive", "",
          {"count": len(directives)})
    return directives


def execute_directives(db, directives: list[dict], actor: str = "director") -> list[dict]:
    """Generate + policy-check + queue content for each directive."""
    from app.modules.content.engine import generate_content, persist_content
    from app.modules.policy.engine import check_content
    from app.modules.publisher.engine import queue_post
    done = []
    for d in directives:
        content = generate_content(d["kind"], d["topic"], d.get("genre", ""),
                                   d.get("artist", ""))
        verdict = check_content(db, content.title, content.body, actor=actor)
        if not verdict["allowed"]:
            done.append({"topic": d["topic"], "status": "blocked",
                         "rule": verdict["rule"]})
            continue
        row = persist_content(db, content, status="queued")
        job = queue_post(db, row.id, "log", delay_minutes=None,
                         country=d.get("market", "US"), actor=actor)
        done.append({"content_id": row.id, "job_id": job.id, "status": "queued"})
    return done
