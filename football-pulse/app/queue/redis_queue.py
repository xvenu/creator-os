"""Redis client + task queue abstraction."""
from __future__ import annotations

import json
import uuid

import redis.asyncio as aioredis

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger("queue")

_client: aioredis.Redis | None = None


def get_redis(settings: Settings) -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _client


def reset_redis() -> None:
    global _client
    _client = None


def queue_key(settings: Settings, agent_name: str) -> str:
    return f"{settings.redis_queue_prefix}:{agent_name}"


async def enqueue_task(settings: Settings, agent_name: str, payload: dict) -> str:
    """Push a task envelope onto the agent queue. Returns task message id."""
    client = get_redis(settings)
    envelope = {"id": str(uuid.uuid4()), "agent": agent_name, "payload": payload}
    await client.rpush(queue_key(settings, agent_name), json.dumps(envelope))
    await client.expire(queue_key(settings, agent_name), settings.redis_default_ttl_seconds)
    log.info("task_enqueued", agent=agent_name, task_id=envelope["id"])
    return envelope["id"]


async def dequeue_task(settings: Settings, agent_name: str, timeout: int = 5) -> dict | None:
    client = get_redis(settings)
    item = await client.blpop(queue_key(settings, agent_name), timeout=timeout)
    if not item:
        return None
    _, raw = item
    return json.loads(raw)


async def queue_length(settings: Settings, agent_name: str) -> int:
    client = get_redis(settings)
    return await client.llen(queue_key(settings, agent_name))
