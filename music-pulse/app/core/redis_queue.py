"""Redis + RQ queue helpers with fakeredis fallback for tests."""
import os
from functools import lru_cache

import redis
from rq import Queue

from app.core.config import get_settings


@lru_cache
def get_redis_client():
    url = os.environ.get("REDIS_URL") or get_settings().redis_url
    if os.environ.get("TESTING") == "1":
        import fakeredis
        return fakeredis.FakeStrictRedis(decode_responses=True)
    return redis.Redis.from_url(url, decode_responses=True)


def get_queue(name: str = "default") -> Queue:
    conn = get_redis_client()
    # RQ needs a non-fake connection in prod; FakeStrictRedis works for enqueue in tests
    # only when is_async=False. We default async True, tests call functions directly.
    return Queue(name, connection=conn)


def enqueue_job(queue_name: str, func, *args, **kwargs):
    q = get_queue(queue_name)
    return q.enqueue(func, *args, **kwargs)
