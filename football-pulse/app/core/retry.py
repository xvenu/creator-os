"""Async retry helpers with exponential backoff (tenacity)."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

P = ParamSpec("P")
T = TypeVar("T")


def async_retry_config(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> dict[str, Any]:
    return {
        "stop": stop_after_attempt(max_attempts),
        "wait": wait_exponential(multiplier=base_delay, min=base_delay, max=max_delay),
        "retry": retry_if_exception_type(exceptions),
        "reraise": True,
    }


async def run_with_retry(
    func: Callable[P, Coroutine[Any, Any, T]],
    *args: P.args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    **kwargs: P.kwargs,
) -> T:
    """Run an async callable with exponential-backoff retries."""
    async for attempt in AsyncRetrying(**async_retry_config(max_attempts, base_delay, max_delay, exceptions)):
        with attempt:
            return await func(*args, **kwargs)
    raise RetryError("unreachable")
