"""Tests for request/notification dispatch outcomes (doc 09 §8, doc 10 §14)."""

from __future__ import annotations

import asyncio

import pytest
from turkish_code.hata import AppError, ErrorKind
from turkish_code.kanal.dagitim import (
    DEADLINE_EXCEEDED_CODE,
    INTERNAL_ERROR_CODE,
    METHOD_NOT_FOUND_CODE,
    dispatch_notification,
    dispatch_request,
)
from turkish_code.kanal.iptal import CancellationRegistry
from turkish_code.kanal.mesaj import (
    ErrorResponse,
    Notification,
    Request,
    SuccessResponse,
)


async def _echo_handler(request: Request) -> SuccessResponse:
    return SuccessResponse(id=request.id, result={"method": request.method})


@pytest.mark.asyncio
async def test_successful_handler_returns_its_response() -> None:
    request = Request(id=1, method="app.ping")
    response = await dispatch_request(_echo_handler, request)
    assert isinstance(response, SuccessResponse)
    assert response.result == {"method": "app.ping"}


@pytest.mark.asyncio
async def test_unknown_method_is_typed_not_found() -> None:
    request = Request(id=1, method="nope.nope")
    response = await dispatch_request(None, request)
    assert isinstance(response, ErrorResponse)
    assert response.error.data is not None
    assert response.error.data["code"] == METHOD_NOT_FOUND_CODE


@pytest.mark.asyncio
async def test_handlers_app_error_is_propagated_as_typed_response() -> None:
    async def _failing(request: Request) -> SuccessResponse:
        raise AppError(
            kind=ErrorKind.PROVIDER,
            code="provider.broken",
            message_key="hata.provider.broken",
            retryable=False,
        )

    response = await dispatch_request(_failing, Request(id=1, method="x"))
    assert isinstance(response, ErrorResponse)
    assert response.error.data is not None
    assert response.error.data["code"] == "provider.broken"


@pytest.mark.asyncio
async def test_unexpected_exception_becomes_typed_internal_error() -> None:
    async def _buggy(request: Request) -> SuccessResponse:
        raise ValueError("a real bug")

    response = await dispatch_request(_buggy, Request(id=1, method="x"))
    assert isinstance(response, ErrorResponse)
    assert response.error.data is not None
    assert response.error.data["code"] == INTERNAL_ERROR_CODE


@pytest.mark.asyncio
async def test_deadline_exceeded_becomes_typed_timeout_error() -> None:
    async def _slow(request: Request) -> SuccessResponse:
        await asyncio.sleep(10)
        return SuccessResponse(id=request.id, result=None)

    request = Request(id=1, method="x", meta={"deadlineMs": 1})
    response = await dispatch_request(_slow, request)
    assert isinstance(response, ErrorResponse)
    assert response.error.data is not None
    assert response.error.data["code"] == DEADLINE_EXCEEDED_CODE


@pytest.mark.asyncio
async def test_no_deadline_lets_a_fast_handler_finish_normally() -> None:
    request = Request(id=1, method="app.ping")
    response = await dispatch_request(_echo_handler, request)
    assert isinstance(response, SuccessResponse)


@pytest.mark.asyncio
async def test_cancel_notification_cancels_the_registered_run() -> None:
    registry = CancellationRegistry()
    token = registry.register("r1")
    note = Notification(method="$/cancel", params={"runId": "r1"})

    await dispatch_notification(note, notification_handlers={}, cancellation=registry)

    assert token.is_cancelled is True


@pytest.mark.asyncio
async def test_cancel_notification_with_unknown_run_id_is_a_noop() -> None:
    registry = CancellationRegistry()
    note = Notification(method="$/cancel", params={"runId": "never-registered"})
    await dispatch_notification(
        note, notification_handlers={}, cancellation=registry
    )  # must not raise


@pytest.mark.asyncio
async def test_unknown_notification_is_silently_ignored() -> None:
    registry = CancellationRegistry()
    note = Notification(method="reasoning.step", params={})
    await dispatch_notification(note, notification_handlers={}, cancellation=registry)


@pytest.mark.asyncio
async def test_registered_notification_handler_is_invoked() -> None:
    received: list[Notification] = []

    async def _handler(note: Notification) -> None:
        received.append(note)

    registry = CancellationRegistry()
    note = Notification(method="log.line", params={"msg": "hi"})
    await dispatch_notification(
        note, notification_handlers={"log.line": _handler}, cancellation=registry
    )

    assert received == [note]
