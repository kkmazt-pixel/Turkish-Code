"""Outbound-request correlation (doc 10 §7) — matches responses to requests
*we* sent, by ``id``. Backs the client side of the bidirectional Core
Channel (doc 10 §6.3: Çekirdek is a client too for ``tool.invoke``/
``permission.*``).
"""

from __future__ import annotations

import asyncio

from turkish_code.kanal.mesaj import RequestId, Response


class PendingRequests:
    """Tracks in-flight outbound requests awaiting a correlated response."""

    def __init__(self) -> None:
        self._pending: dict[RequestId, asyncio.Future[Response]] = {}

    def create(self, request_id: RequestId) -> asyncio.Future[Response]:
        """Register ``request_id`` as pending; the caller awaits the returned future."""
        future: asyncio.Future[Response] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        return future

    def resolve(self, response: Response) -> bool:
        """Resolve the pending future for ``response.id``, if tracked.

        Returns ``True`` if a pending request was found and resolved,
        ``False`` for a missing/unknown/duplicate/late id (doc 10 §17) —
        never raises. An ``ErrorResponse`` with no ``id`` (a top-level parse
        error) can never correlate to a pending request.
        """
        if response.id is None:
            return False
        future = self._pending.pop(response.id, None)
        if future is None or future.done():
            return False
        future.set_result(response)
        return True

    def cancel(self, request_id: RequestId) -> None:
        """Cancel the pending future for ``request_id``, if tracked."""
        future = self._pending.pop(request_id, None)
        if future is not None and not future.done():
            future.cancel()

    def __len__(self) -> int:
        return len(self._pending)
