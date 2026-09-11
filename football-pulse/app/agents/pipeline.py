"""Phase 4 pipeline helpers: next-stage task emission + session resolution."""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Task


async def emit_next_task(
    session: AsyncSession,
    source_agent: str,
    spec: dict,
    ref_key: str = "ref_id",
    ref_id: str = "",
) -> Task | None:
    """Create the next pipeline stage's task when payload carries `emit_task`.

    spec shape: {"agent": <agent_name>, "kind": <task_kind>, "extra": {...}}.
    Returns the created Task or None when no spec is present.
    """
    if not isinstance(spec, dict) or not spec.get("agent") or not spec.get("kind"):
        return None
    task = Task(
        agent_name=str(spec["agent"]),
        kind=str(spec["kind"]),
        payload={
            "source": source_agent,
            ref_key: ref_id,
            **dict(spec.get("extra", {})),
        },
        status="queued",
    )
    session.add(task)
    await session.flush()
    return task


def make_resolver(module_globals: dict) -> Callable:
    """Build a lazy session-factory resolver honoring test overrides."""
    def _resolve() -> Callable:
        factory = module_globals.get("_session_factory")
        if factory is not None:
            return factory
        from app.core.config import get_settings
        from app.db.session import get_session_factory

        return get_session_factory(get_settings())

    return _resolve
