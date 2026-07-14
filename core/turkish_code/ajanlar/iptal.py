"""Cooperative cancellation for agent runs (doc 18 §9, doc 10 §10).

A run-scoped analog of the tool-call cancellation in the Tool Runtime: each
in-flight ``run_id`` gets a :class:`CancellationToken` the agent checks
cooperatively, and the dispatcher cancels by ``run_id`` — cancellation is meant
to propagate through the whole run (doc 18 §9). Kept in ``ajanlar`` so the Agent
Runtime owns its own cancellation surface. Cancelling an unknown or finished run
is a no-op (idempotent, doc 10 §10).
"""

from __future__ import annotations

import asyncio


class CancellationToken:
    """A cooperative cancellation flag for one agent run (doc 18 §9)."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        """Mark this run cancelled. Idempotent."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        """Suspend until cancelled — the dispatcher races this against the run."""
        await self._event.wait()


class CancellationRegistry:
    """Tracks one :class:`CancellationToken` per in-flight ``run_id`` (doc 18 §9)."""

    def __init__(self) -> None:
        self._tokens: dict[str, CancellationToken] = {}

    def register(self, run_id: str) -> CancellationToken:
        """Create and track a fresh token for ``run_id``, replacing any prior one."""
        token = CancellationToken()
        self._tokens[run_id] = token
        return token

    def cancel(self, run_id: str) -> None:
        """Cancel ``run_id`` if tracked; a no-op otherwise (doc 10 §10)."""
        token = self._tokens.get(run_id)
        if token is not None:
            token.cancel()

    def unregister(self, run_id: str) -> None:
        """Stop tracking ``run_id`` (call when its run finishes)."""
        self._tokens.pop(run_id, None)

    def token_for(self, run_id: str) -> CancellationToken | None:
        """The tracked token for ``run_id``, or ``None`` if not tracked."""
        return self._tokens.get(run_id)
