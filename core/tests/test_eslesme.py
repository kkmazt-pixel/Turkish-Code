"""Tests for outbound-request correlation (doc 10 §7)."""

from __future__ import annotations

import asyncio

import pytest
from turkish_code.kanal.eslesme import PendingRequests
from turkish_code.kanal.mesaj import ErrorResponse, JsonRpcError, SuccessResponse


@pytest.mark.asyncio
async def test_resolve_completes_the_pending_future() -> None:
    pending = PendingRequests()
    future = pending.create(1)

    resolved = pending.resolve(SuccessResponse(id=1, result={"ok": True}))

    assert resolved is True
    assert await future == SuccessResponse(id=1, result={"ok": True})


def test_resolve_returns_false_for_unknown_id() -> None:
    pending = PendingRequests()
    resolved = pending.resolve(SuccessResponse(id=999, result=None))
    assert resolved is False


def test_resolve_returns_false_for_error_response_with_no_id() -> None:
    pending = PendingRequests()
    error = ErrorResponse(
        id=None, error=JsonRpcError(code=-32700, message="parse error")
    )
    assert pending.resolve(error) is False


@pytest.mark.asyncio
async def test_resolve_is_one_shot() -> None:
    pending = PendingRequests()
    pending.create(1)
    pending.resolve(SuccessResponse(id=1, result=None))

    second = pending.resolve(SuccessResponse(id=1, result="late duplicate"))
    assert second is False


def test_cancel_unknown_id_is_a_noop() -> None:
    pending = PendingRequests()
    pending.cancel("never-created")  # must not raise


@pytest.mark.asyncio
async def test_cancel_cancels_the_pending_future() -> None:
    pending = PendingRequests()
    future = pending.create(1)
    pending.cancel(1)
    with pytest.raises(asyncio.CancelledError):
        await future


@pytest.mark.asyncio
async def test_len_reflects_pending_count() -> None:
    pending = PendingRequests()
    pending.create(1)
    pending.create(2)
    assert len(pending) == 2
    pending.resolve(SuccessResponse(id=1, result=None))
    assert len(pending) == 1
