"""Tests for cooperative cancellation (doc 10 §10)."""

from __future__ import annotations

import asyncio

import pytest
from turkish_code.kanal.iptal import CancellationRegistry, CancellationToken


def test_token_starts_not_cancelled() -> None:
    assert CancellationToken().is_cancelled is False


def test_cancel_marks_token_cancelled() -> None:
    token = CancellationToken()
    token.cancel()
    assert token.is_cancelled is True


def test_cancel_is_idempotent() -> None:
    token = CancellationToken()
    token.cancel()
    token.cancel()
    assert token.is_cancelled is True


@pytest.mark.asyncio
async def test_wait_resolves_once_cancelled() -> None:
    token = CancellationToken()

    async def _cancel_soon() -> None:
        await asyncio.sleep(0)
        token.cancel()

    await asyncio.gather(token.wait(), _cancel_soon())
    assert token.is_cancelled is True


def test_register_tracks_a_token_for_the_run() -> None:
    registry = CancellationRegistry()
    token = registry.register("r1")
    assert registry.token_for("r1") is token


def test_cancel_unknown_run_id_is_a_noop() -> None:
    registry = CancellationRegistry()
    registry.cancel("never-registered")  # must not raise


def test_cancel_propagates_to_the_registered_token() -> None:
    registry = CancellationRegistry()
    token = registry.register("r1")
    registry.cancel("r1")
    assert token.is_cancelled is True


def test_unregister_removes_the_token() -> None:
    registry = CancellationRegistry()
    registry.register("r1")
    registry.unregister("r1")
    assert registry.token_for("r1") is None


def test_cancel_after_unregister_is_a_noop() -> None:
    """Cancelling an already-finished run must not resurrect or error (doc 10 §10)."""
    registry = CancellationRegistry()
    token = registry.register("r1")
    registry.unregister("r1")
    registry.cancel("r1")
    assert token.is_cancelled is False
