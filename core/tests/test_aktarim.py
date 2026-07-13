"""Tests for :class:`StdioTransport` over real OS pipes (doc 09 §5/§6)."""

from __future__ import annotations

import pytest

from tests.pipes import real_transport_pair


@pytest.mark.asyncio
async def test_write_then_read_round_trips_over_a_real_pipe() -> None:
    a, b = await real_transport_pair()
    await a.write_frame(b'{"hello":"world"}')
    assert await b.read_frame() == b'{"hello":"world"}'


@pytest.mark.asyncio
async def test_multiple_frames_preserve_order() -> None:
    a, b = await real_transport_pair()
    for payload in (b"one", b"two", b"three"):
        await a.write_frame(payload)

    received = [await b.read_frame() for _ in range(3)]
    assert received == [b"one", b"two", b"three"]


@pytest.mark.asyncio
async def test_bidirectional_traffic_on_one_pair() -> None:
    a, b = await real_transport_pair()
    await a.write_frame(b"ping")
    await b.write_frame(b"pong")

    assert await b.read_frame() == b"ping"
    assert await a.read_frame() == b"pong"


@pytest.mark.asyncio
async def test_read_frame_returns_none_after_writer_closes() -> None:
    a, b = await real_transport_pair()
    await a.aclose()
    assert await b.read_frame() is None
