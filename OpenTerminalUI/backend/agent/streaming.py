from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator

from backend.agent import events


async def complete_with_status(
    provider: Any, messages: Any, **kwargs: Any,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run ``provider.complete`` while live-streaming its progress.

    The provider reports transient progress (model attempts, rate-limit
    backoffs) via an ``on_status`` callback. Since ``complete`` is a single
    awaitable, we run it as a task and drain status notes from a queue so the
    agent event stream stays alive during long retry/backoff windows that would
    otherwise look frozen.

    Yields ``status`` events as they arrive and finally a single ``result``
    event carrying the ``AssistantMessage``. If the completion fails, the
    underlying exception propagates from the final ``next()`` (callers keep
    their existing try/except around it).
    """
    queue: asyncio.Queue[str] = asyncio.Queue()

    async def on_status(text: str) -> None:
        queue.put_nowait(text)

    task = asyncio.ensure_future(
        provider.complete(messages, on_status=on_status, **kwargs)
    )
    try:
        while not task.done():
            drained = False
            while not queue.empty():
                yield events.status(queue.get_nowait())
                drained = True
            if not drained:
                await asyncio.sleep(0.2)
        while not queue.empty():
            yield events.status(queue.get_nowait())
        # Raises here if the completion failed — propagates to the caller.
        yield {"type": "result", "message": task.result()}
    finally:
        if not task.done():
            task.cancel()
