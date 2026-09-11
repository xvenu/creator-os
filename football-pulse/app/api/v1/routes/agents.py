"""Agent + task endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext
from app.agents.registry import registry
from app.api.deps import get_db
from app.schemas import TaskIn, TaskOut
from app.services import task_service

router = APIRouter(tags=["agents"])


@router.get("")
async def list_agents() -> dict:
    return {"agents": registry.list()}


@router.get("/{name}/health")
async def agent_health(name: str) -> dict:
    try:
        agent = registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {name}")
    return await agent.health()


@router.post("/{name}/run")
async def run_agent(name: str, payload: dict | None = None) -> dict:
    try:
        agent = registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {name}")
    ctx = AgentContext(payload=payload or {})
    result = await agent.run(ctx)
    return result.model_dump(mode="json")


@router.post("/tasks", response_model=TaskOut)
async def create_task(data: TaskIn, session: AsyncSession = Depends(get_db)) -> TaskOut:
    try:
        registry.get(data.agent_name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {data.agent_name}")
    task = await task_service.create_task(session, data)
    return TaskOut(
        id=task.id,
        agent_name=task.agent_name,
        kind=task.kind,
        status=task.status,
        attempts=task.attempts,
        payload=task.payload,
        result=task.result,
        error=task.error,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("/tasks/{task_id}", response_model=TaskOut)
async def fetch_task(task_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> TaskOut:
    task = await task_service.get_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskOut(
        id=task.id,
        agent_name=task.agent_name,
        kind=task.kind,
        status=task.status,
        attempts=task.attempts,
        payload=task.payload,
        result=task.result,
        error=task.error,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("/tasks/{task_id}/execute")
async def execute_task(task_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> dict:
    task = await task_service.get_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    agent = registry.get(task.agent_name)
    task = await task_service.mark_running(session, task)
    ctx = AgentContext(
        task_id=task.id, payload=task.payload, timeout_seconds=120.0
    )
    result = await agent.run(ctx)
    if result.status.value == "succeeded":
        await task_service.mark_finished(session, task, result.output)
    else:
        await task_service.mark_failed(session, task, result.error or "unknown error")
    return result.model_dump(mode="json")
