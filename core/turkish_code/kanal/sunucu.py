"""Core Channel server + client (doc 10) — the concrete implementation.

:class:`AsyncCoreChannel` owns exactly one reader loop and one writer per
:class:`~turkish_code.kanal.aktarim.Transport` (doc 09 §6): inbound requests
are dispatched as concurrent tasks (no head-of-line blocking, doc 10 §7),
inbound notifications route to ``$/cancel`` or a registered handler
(doc 10 §17), and inbound responses resolve our own outbound requests
(doc 10 §6.3 — the channel is bidirectional).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from turkish_code.kanal.aktarim import Transport
from turkish_code.kanal.dagitim import (
    Handler,
    NotificationHandler,
    dispatch_notification,
    dispatch_request,
)
from turkish_code.kanal.dogrulama import parse_frame
from turkish_code.kanal.eslesme import PendingRequests
from turkish_code.kanal.iptal import CancellationRegistry, CancellationToken
from turkish_code.kanal.mesaj import Notification, Request, RequestId, Response


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


class AsyncCoreChannel:
    """A real, bidirectional Core Channel over one :class:`Transport` (doc 10)."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        self._handlers: dict[str, Handler] = {}
        self._notification_handlers: dict[str, NotificationHandler] = {}
        self._pending = PendingRequests()
        self._cancellation = CancellationRegistry()
        self._write_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[None]] = set()
        self._shutdown = asyncio.Event()
        self._next_id = 0

    def register(self, method: str, handler: Handler) -> None:
        """Bind ``handler`` to inbound requests for ``method`` (doc 09 §8)."""
        self._handlers[method] = handler

    def on_notification(self, method: str, handler: NotificationHandler) -> None:
        """Bind ``handler`` to inbound notifications for ``method`` (doc 10 §17)."""
        self._notification_handlers[method] = handler

    def register_run(self, run_id: str) -> CancellationToken:
        """Track a cancellable run so ``$/cancel`` can reach it (doc 10 §10)."""
        return self._cancellation.register(run_id)

    def cancellation_token_for(self, run_id: str) -> CancellationToken | None:
        """The token for ``run_id``, if it's tracked (doc 10 §10)."""
        return self._cancellation.token_for(run_id)

    def notify(self, note: Notification) -> None:
        """Enqueue an outbound notification (doc 09 §6) without blocking the caller."""
        self._track(asyncio.ensure_future(self._write(note.to_wire())))

    async def request(
        self,
        method: str,
        params: Mapping[str, object] | None = None,
        *,
        meta: Mapping[str, object] | None = None,
    ) -> Response:
        """Send an outbound request (Ç→K direction, e.g. ``tool.invoke``,
        doc 10 §6.3) and await its correlated response."""
        request_id = self._next_request_id()
        outgoing = Request(id=request_id, method=method, params=params, meta=meta)
        future = self._pending.create(request_id)
        await self._write(outgoing.to_wire())
        return await future

    async def serve(self) -> None:
        """Read, dispatch, and respond until shutdown (doc 09 §11)."""
        reader_task = asyncio.ensure_future(self._read_loop())
        await self._shutdown.wait()
        reader_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reader_task
        await self._cancel_in_flight()

    def request_shutdown(self) -> None:
        """Signal :meth:`serve` to return (doc 09 §11 ``app.shutdown``)."""
        self._shutdown.set()

    async def aclose(self) -> None:
        """Close the underlying transport."""
        await self._transport.aclose()

    def _next_request_id(self) -> RequestId:
        self._next_id += 1
        return f"core-{self._next_id}"

    async def _read_loop(self) -> None:
        while True:
            payload = await self._transport.read_frame()
            if payload is None:
                self.request_shutdown()
                return
            self._handle_frame(payload)

    def _handle_frame(self, payload: bytes) -> None:
        try:
            message = parse_frame(payload)
        except (
            Exception
        ):  # noqa: BLE001 - malformed frame: drop, never crash (doc 10 §14)
            return

        if isinstance(message, Request):
            self._track(asyncio.ensure_future(self._handle_request(message)))
        elif isinstance(message, Notification):
            self._track(asyncio.ensure_future(self._handle_notification(message)))
        else:
            self._pending.resolve(message)

    async def _handle_request(self, request: Request) -> None:
        handler = self._handlers.get(request.method)
        response = await dispatch_request(handler, request)
        await self._write(response.to_wire())

    async def _handle_notification(self, note: Notification) -> None:
        await dispatch_notification(
            note,
            notification_handlers=self._notification_handlers,
            cancellation=self._cancellation,
        )

    async def _write(self, wire: dict[str, object]) -> None:
        payload = json.dumps(wire).encode("utf-8")
        async with self._write_lock:
            await self._transport.write_frame(payload)

    def _track(self, task: asyncio.Task[None]) -> None:
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _cancel_in_flight(self) -> None:
        pending_tasks = list(self._tasks)
        for task in pending_tasks:
            task.cancel()
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)
