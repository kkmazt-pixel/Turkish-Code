"""Core Channel server abstraction (doc 10) — interface only.

Defines the seam subsystems use to expose methods over the Core Channel. The
concrete implementation (stdio framing, the single writer, dispatch, streaming,
cancellation — doc 09 §6/§8) is a deliberately deferred later increment; wiring
it now would be unverifiable placeholder code.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from turkish_code.kanal.mesaj import (
    ErrorResponse,
    Notification,
    Request,
    SuccessResponse,
)

Response = SuccessResponse | ErrorResponse
"""A handler's result: either a success or a typed error response."""

Handler = Callable[[Request], Awaitable[Response]]
"""An async function that handles one Core Channel request (doc 09 §8)."""


@runtime_checkable
class CoreChannel(Protocol):
    """The Core Channel server contract (doc 10).

    A concrete server owns exactly one stdout writer (doc 09 §6) and routes each
    request to the handler registered for its method namespace (doc 09 §8).
    """

    def register(self, method: str, handler: Handler) -> None:
        """Bind ``handler`` to a request ``method`` (e.g. ``"memory.recall"``)."""
        ...

    def notify(self, note: Notification) -> None:
        """Enqueue an outbound notification on the single writer (doc 09 §6)."""
        ...

    async def serve(self) -> None:
        """Read, dispatch, and respond to requests until shutdown (doc 09 §11)."""
        ...
