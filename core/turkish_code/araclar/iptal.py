"""Cooperative cancellation for tool calls (doc 20 §14, doc 10 §10).

A call-scoped analog of the run-level cancellation in the channel: each in-flight
``call_id`` gets a :class:`CancellationToken` the tool checks cooperatively, and
the dispatcher cancels by ``call_id``. Kept in ``araclar`` (not imported from
``kanal``) so the tool runtime stays independent of the IPC transport — clean
import direction — and because the scope key differs (call vs run). Cancelling an
unknown or finished call is a no-op (idempotent, doc 10 §10).
"""

from __future__ import annotations

import asyncio


class CancellationToken:
    """A cooperative cancellation flag for one tool call (doc 20 §14)."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        """Mark this call cancelled. Idempotent."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        """Suspend until cancelled — the dispatcher races this against execution."""
        await self._event.wait()


class CancellationRegistry:
    """Tracks one :class:`CancellationToken` per in-flight ``call_id`` (doc 20 §14)."""

    def __init__(self) -> None:
        self._tokens: dict[str, CancellationToken] = {}

    def register(self, call_id: str) -> CancellationToken:
        """Create and track a fresh token for ``call_id``, replacing any prior one."""
        token = CancellationToken()
        self._tokens[call_id] = token
        return token

    def cancel(self, call_id: str) -> None:
        """Cancel ``call_id`` if tracked; a no-op otherwise (doc 10 §10)."""
        token = self._tokens.get(call_id)
        if token is not None:
            token.cancel()

    def unregister(self, call_id: str) -> None:
        """Stop tracking ``call_id`` (call when its invocation finishes)."""
        self._tokens.pop(call_id, None)

    def token_for(self, call_id: str) -> CancellationToken | None:
        """The tracked token for ``call_id``, or ``None`` if not tracked."""
        return self._tokens.get(call_id)
