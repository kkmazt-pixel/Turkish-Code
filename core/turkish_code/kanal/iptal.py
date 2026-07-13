"""Cooperative cancellation (doc 10 §10) — ``$/cancel { runId }``.

A run's handler cooperatively checks its :class:`CancellationToken`; cancelling
an unknown or already-finished ``runId`` is a no-op (idempotent, doc 10 §10).
"""

from __future__ import annotations

import asyncio


class CancellationToken:
    """A cooperative cancellation flag for one run (doc 10 §10)."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        """Mark this token cancelled. Idempotent."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        """Suspend until cancelled — for a cooperative checkpoint."""
        await self._event.wait()


class CancellationRegistry:
    """Tracks one :class:`CancellationToken` per in-flight ``runId`` (doc 10 §10)."""

    def __init__(self) -> None:
        self._tokens: dict[str, CancellationToken] = {}

    def register(self, run_id: str) -> CancellationToken:
        """Create and track a fresh token for ``run_id``, replacing any prior one."""
        token = CancellationToken()
        self._tokens[run_id] = token
        return token

    def cancel(self, run_id: str) -> None:
        """Cancel ``run_id`` if it's tracked; a no-op otherwise (doc 10 §10)."""
        token = self._tokens.get(run_id)
        if token is not None:
            token.cancel()

    def unregister(self, run_id: str) -> None:
        """Stop tracking ``run_id`` (call when its run finishes)."""
        self._tokens.pop(run_id, None)

    def token_for(self, run_id: str) -> CancellationToken | None:
        """The tracked token for ``run_id``, or ``None`` if not tracked."""
        return self._tokens.get(run_id)
