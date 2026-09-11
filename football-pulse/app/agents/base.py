"""Agent framework: types, base class, registry."""
from __future__ import annotations

import abc
import asyncio
import datetime as dt
import uuid
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.retry import run_with_retry


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AgentContext(BaseModel):
    run_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    task_id: uuid.UUID | None = None
    payload: dict = Field(default_factory=dict)
    timeout_seconds: float = 120.0

    model_config = {"arbitrary_types_allowed": True}


class AgentResult(BaseModel):
    agent_name: str
    run_id: uuid.UUID
    status: AgentStatus = AgentStatus.SUCCEEDED
    output: dict = Field(default_factory=dict)
    error: str | None = None
    started_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    finished_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))


@dataclass
class AgentMetadata:
    name: str
    description: str
    version: str = "0.1.0"


class BaseAgent(abc.ABC):
    """All 12 FootballPulse agents derive from this. Async-first, typed, retryable."""

    metadata: AgentMetadata

    def __init__(self) -> None:
        self._log = get_logger(f"agent.{self.metadata.name}")
        self._status = AgentStatus.IDLE

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def status(self) -> AgentStatus:
        return self._status

    @abc.abstractmethod
    async def handle(self, ctx: AgentContext) -> dict:
        """Agent-specific logic. Must be implemented by subclasses."""
        raise NotImplementedError

    async def run(self, ctx: AgentContext | None = None, max_attempts: int = 3) -> AgentResult:
        ctx = ctx or AgentContext()
        started = dt.datetime.now(dt.timezone.utc)
        self._status = AgentStatus.RUNNING
        self._log.info("agent_run_started", run_id=str(ctx.run_id), payload_keys=list(ctx.payload.keys()))
        try:

            async def _exec() -> dict:
                return await asyncio.wait_for(self.handle(ctx), timeout=ctx.timeout_seconds)

            output = await run_with_retry(_exec, max_attempts=max_attempts)
            self._status = AgentStatus.SUCCEEDED
            return AgentResult(
                agent_name=self.name,
                run_id=ctx.run_id,
                status=AgentStatus.SUCCEEDED,
                output=output,
                started_at=started,
                finished_at=dt.datetime.now(dt.timezone.utc),
            )
        except Exception as exc:  # noqa: BLE001
            self._status = AgentStatus.FAILED
            self._log.error("agent_run_failed", run_id=str(ctx.run_id), error=str(exc))
            return AgentResult(
                agent_name=self.name,
                run_id=ctx.run_id,
                status=AgentStatus.FAILED,
                output={},
                error=str(exc),
                started_at=started,
                finished_at=dt.datetime.now(dt.timezone.utc),
            )

    async def health(self) -> dict:
        return {"name": self.name, "status": self._status.value, "version": self.metadata.version}
