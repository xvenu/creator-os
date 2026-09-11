"""Task persistence service (PostgreSQL-backed)."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Task
from app.schemas import TaskIn


async def create_task(session: AsyncSession, data: TaskIn) -> Task:
    task = Task(
        agent_name=data.agent_name,
        kind=data.kind,
        payload=data.payload,
        max_attempts=data.max_attempts,
        status="queued",
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_task(session: AsyncSession, task_id: uuid.UUID) -> Task | None:
    return await session.get(Task, task_id)


async def list_tasks(session: AsyncSession, agent_name: str | None = None, limit: int = 50) -> list[Task]:
    stmt = select(Task).order_by(Task.created_at.desc()).limit(limit)
    if agent_name:
        stmt = select(Task).where(Task.agent_name == agent_name).order_by(Task.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_running(session: AsyncSession, task: Task) -> Task:
    task.status = "running"
    task.attempts += 1
    task.started_at = dt.datetime.now(dt.timezone.utc)
    await session.commit()
    await session.refresh(task)
    return task


async def mark_finished(session: AsyncSession, task: Task, result: dict) -> Task:
    task.status = "succeeded"
    task.result = result
    task.finished_at = dt.datetime.now(dt.timezone.utc)
    await session.commit()
    await session.refresh(task)
    return task


async def mark_failed(session: AsyncSession, task: Task, error: str) -> Task:
    task.error = error
    task.finished_at = dt.datetime.now(dt.timezone.utc)
    task.status = "failed" if task.attempts >= task.max_attempts else "queued"
    await session.commit()
    await session.refresh(task)
    return task
