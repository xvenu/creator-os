"""Phase 3 decision queues.

Canonical queue names (as specified):
- fp:queue:prediction → prediction agent
- fp:queue:executive → executive agent
- fp:queue:opportunity → content_opportunity agent
"""
from __future__ import annotations

import json
import uuid

from app.core.config import Settings
from app.core.logging import get_logger
from app.queue.redis_queue import get_redis

log = get_logger("queue.decision")

QUEUE_TO_AGENT: dict[str, str] = {
    "fp:queue:prediction": "prediction",
    "fp:queue:executive": "executive",
    "fp:queue:opportunity": "content_opportunity",
}

AGENT_TO_QUEUE: dict[str, str] = {v: k for k, v in QUEUE_TO_AGENT.items()}


def decision_queue_names() -> list[str]:
    return sorted(QUEUE_TO_AGENT.keys())


def queue_for_agent(agent_name: str) -> str | None:
    return AGENT_TO_QUEUE.get(agent_name)


async def enqueue_decision(queue_name: str, payload: dict, settings: Settings) -> str:
    """Push a payload envelope onto a decision queue."""
    if queue_name not in QUEUE_TO_AGENT:
        raise ValueError(f"Unknown decision queue: {queue_name}")
    client = get_redis(settings)
    envelope = {
        "id": str(uuid.uuid4()),
        "agent": QUEUE_TO_AGENT[queue_name],
        "payload": payload,
    }
    await client.rpush(queue_name, json.dumps(envelope))
    await client.expire(queue_name, settings.redis_default_ttl_seconds)
    log.info("decision_enqueued", queue=queue_name, agent=envelope["agent"], job_id=envelope["id"])
    return envelope["id"]


async def dequeue_decision(queue_name: str, settings: Settings, timeout: int = 5) -> dict | None:
    client = get_redis(settings)
    item = await client.blpop(queue_name, timeout=timeout)
    if not item:
        return None
    _, raw = item
    return json.loads(raw)


async def decision_queue_length(queue_name: str, settings: Settings) -> int:
    client = get_redis(settings)
    return await client.llen(queue_name)
