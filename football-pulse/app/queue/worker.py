"""Background worker: pulls Redis queue, dispatches to agents, persists results."""
from __future__ import annotations

import asyncio

from app.agents import register_all_agents
from app.agents.base import AgentContext
from app.agents.registry import registry
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_session_factory
from app.queue.content_queues import QUEUE_TO_AGENT as CONTENT_QUEUES
from app.queue.content_queues import dequeue_content
from app.queue.decision_queues import QUEUE_TO_AGENT as DECISION_QUEUES
from app.queue.decision_queues import dequeue_decision
from app.queue.intel_queues import QUEUE_TO_AGENT, dequeue_intel
from app.queue.redis_queue import dequeue_task
from app.queue.zoza_queues import QUEUE_TO_AGENT as ZOZA_QUEUES
from app.queue.zoza_queues import dequeue_zoza
from app.services import task_service

log = get_logger("worker")


async def run_zoza_queue_once(queue_name: str) -> bool:
    """Consume one Zoza dispatch/monitor job: submit → track → collect exports."""
    settings = get_settings()
    envelope = await dequeue_zoza(queue_name, settings, timeout=2)
    if not envelope:
        return False
    agent = registry.get(envelope.get("agent") or ZOZA_QUEUES[queue_name])
    ctx = AgentContext(payload=envelope.get("payload", {}))
    result = await agent.run(ctx)
    log.info(
        "zoza_task_done",
        queue=queue_name,
        agent=agent.name,
        status=result.status.value,
        run_id=str(ctx.run_id),
        job_id=envelope.get("id"),
    )
    return True


async def run_decision_queue_once(queue_name: str) -> bool:
    """Consume one job from a decision queue: process → persist → memory → tasks."""
    settings = get_settings()
    envelope = await dequeue_decision(queue_name, settings, timeout=2)
    if not envelope:
        return False
    agent = registry.get(envelope.get("agent") or DECISION_QUEUES[queue_name])
    ctx = AgentContext(payload=envelope.get("payload", {}))
    result = await agent.run(ctx)
    # Decision agents persist results, update memory and generate tasks in handle().
    log.info(
        "decision_task_done",
        queue=queue_name,
        agent=agent.name,
        status=result.status.value,
        run_id=str(ctx.run_id),
        job_id=envelope.get("id"),
    )
    return True


async def run_intel_queue_once(queue_name: str) -> bool:
    """Consume one job from an intelligence queue: process → persist → log."""
    settings = get_settings()
    envelope = await dequeue_intel(queue_name, settings, timeout=2)
    if not envelope:
        return False
    agent = registry.get(envelope.get("agent") or QUEUE_TO_AGENT[queue_name])
    ctx = AgentContext(payload=envelope.get("payload", {}))
    result = await agent.run(ctx)
    # Agents persist their own intelligence results inside handle().
    log.info(
        "intel_task_done",
        queue=queue_name,
        agent=agent.name,
        status=result.status.value,
        run_id=str(ctx.run_id),
        job_id=envelope.get("id"),
    )
    return True


async def run_content_queue_once(queue_name: str) -> bool:
    """Consume one job from a content-pipeline queue.

    Content agents persist assets, update memory, and emit the next
    stage's task when the payload carries `emit_task`.
    """
    settings = get_settings()
    envelope = await dequeue_content(queue_name, settings, timeout=2)
    if not envelope:
        return False
    agent = registry.get(envelope.get("agent") or CONTENT_QUEUES[queue_name])
    ctx = AgentContext(payload=envelope.get("payload", {}))
    result = await agent.run(ctx)
    log.info(
        "content_task_done",
        queue=queue_name,
        agent=agent.name,
        status=result.status.value,
        run_id=str(ctx.run_id),
        job_id=envelope.get("id"),
    )
    return True


async def run_once(agent_name: str) -> bool:
    settings = get_settings()
    envelope = await dequeue_task(settings, agent_name, timeout=2)
    if not envelope:
        return False
    agent = registry.get(agent_name)
    ctx = AgentContext(payload=envelope.get("payload", {}))
    result = await agent.run(ctx)
    log.info(
        "worker_task_done",
        agent=agent_name,
        status=result.status.value,
        run_id=str(ctx.run_id),
    )
    return True


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    register_all_agents()
    log.info("worker_started", agents=registry.names())
    while True:
        worked = False
        for name in registry.names():
            try:
                if await run_once(name):
                    worked = True
            except Exception as exc:  # noqa: BLE001
                log.error("worker_error", agent=name, error=str(exc))
        for queue_name in QUEUE_TO_AGENT:
            try:
                if await run_intel_queue_once(queue_name):
                    worked = True
            except Exception as exc:  # noqa: BLE001
                log.error("intel_worker_error", queue=queue_name, error=str(exc))
        for queue_name in DECISION_QUEUES:
            try:
                if await run_decision_queue_once(queue_name):
                    worked = True
            except Exception as exc:  # noqa: BLE001
                log.error("decision_worker_error", queue=queue_name, error=str(exc))
        for queue_name in CONTENT_QUEUES:
            try:
                if await run_content_queue_once(queue_name):
                    worked = True
            except Exception as exc:  # noqa: BLE001
                log.error("content_worker_error", queue=queue_name, error=str(exc))
        for queue_name in ZOZA_QUEUES:
            try:
                if await run_zoza_queue_once(queue_name):
                    worked = True
            except Exception as exc:  # noqa: BLE001
                log.error("zoza_worker_error", queue=queue_name, error=str(exc))
        if not worked:
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
