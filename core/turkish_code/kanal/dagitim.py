"""Request/notification dispatch outcomes (doc 09 §8, doc 10 §14, doc 38 §7).

Pure(ish) dispatch logic — given a handler and a request, produce the
``Response`` to send back, with timeout bounding (doc 10 §14) and typed
error-wrapping so a handler bug never crashes the read loop (doc 09 §17).
Kept separate from :mod:`~turkish_code.kanal.sunucu` so this is testable
without a real transport.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from turkish_code.hata import AppError, ErrorKind
from turkish_code.kanal.iptal import CancellationRegistry
from turkish_code.kanal.mesaj import (
    Notification,
    Request,
    Response,
    error_response_from_app_error,
)

CANCEL_METHOD = "$/cancel"

Handler = Callable[[Request], Awaitable[Response]]
"""An async function that handles one inbound Core Channel request (doc 09 §8)."""

NotificationHandler = Callable[[Notification], Awaitable[None]]

METHOD_NOT_FOUND_CODE = "ipc.method_not_found"
DEADLINE_EXCEEDED_CODE = "ipc.deadline_exceeded"
INTERNAL_ERROR_CODE = "ipc.internal_error"


async def dispatch_request(handler: Handler | None, request: Request) -> Response:
    """Run ``handler`` for ``request``, bounded by its deadline (doc 10 §14).

    Returns a typed error response instead of raising for every failure mode:
    unknown method, deadline exceeded, a handler's own ``AppError``, or an
    unexpected exception (never a raw traceback to the wire, doc 38 §20/§21).
    """
    if handler is None:
        return error_response_from_app_error(request.id, _method_not_found(request))

    deadline_seconds = _deadline_seconds(request)
    try:
        if deadline_seconds is not None:
            async with asyncio.timeout(deadline_seconds):
                return await handler(request)
        return await handler(request)
    except TimeoutError:
        return error_response_from_app_error(request.id, _deadline_exceeded())
    except AppError as err:
        return error_response_from_app_error(request.id, err)
    except Exception as exc:  # noqa: BLE001 - top boundary: never crash the loop
        return error_response_from_app_error(request.id, _internal_error(exc))


async def dispatch_notification(
    note: Notification,
    *,
    notification_handlers: dict[str, NotificationHandler],
    cancellation: CancellationRegistry,
) -> None:
    """Route ``note`` to ``$/cancel`` handling, a registered handler, or
    silently ignore it if unknown (doc 10 §17 — notifications never error)."""
    if note.method == CANCEL_METHOD:
        run_id = (note.params or {}).get("runId")
        if isinstance(run_id, str):
            cancellation.cancel(run_id)
        return

    handler = notification_handlers.get(note.method)
    if handler is not None:
        await handler(note)


def _deadline_seconds(request: Request) -> float | None:
    deadline_ms = request.deadline_ms
    return deadline_ms / 1000 if deadline_ms is not None else None


def _method_not_found(request: Request) -> AppError:
    return AppError(
        kind=ErrorKind.NOT_FOUND,
        code=METHOD_NOT_FOUND_CODE,
        message_key="hata.ipc.method_not_found",
        retryable=False,
        context={"method": request.method},
    )


def _deadline_exceeded() -> AppError:
    return AppError(
        kind=ErrorKind.TIMEOUT,
        code=DEADLINE_EXCEEDED_CODE,
        message_key="hata.ipc.deadline_exceeded",
        retryable=True,
    )


def _internal_error(exc: Exception) -> AppError:
    return AppError(
        kind=ErrorKind.INTERNAL,
        code=INTERNAL_ERROR_CODE,
        message_key="hata.ipc.internal_error",
        retryable=False,
        detail=str(exc),
    )
