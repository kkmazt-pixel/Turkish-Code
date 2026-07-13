"""Tests for the length-prefixed frame codec (doc 10 §6.1)."""

from __future__ import annotations

import struct

import pytest
from turkish_code.kanal.cerceve import (
    MAX_FRAME_BYTES,
    IncompleteFrame,
    decode_frame,
    encode_frame,
)


class _BufferReader:
    """A fake ``read_exactly`` fed from an in-memory buffer (no real I/O)."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    async def read_exactly(self, n: int) -> bytes:
        available = self._data[self._pos : self._pos + n]
        self._pos += len(available)
        if len(available) < n:
            raise IncompleteFrame(expected=n, partial=available)
        return available


@pytest.mark.asyncio
async def test_round_trip_single_frame() -> None:
    payload = b'{"hello":"world"}'
    reader = _BufferReader(encode_frame(payload))
    decoded = await decode_frame(reader.read_exactly)
    assert decoded == payload


@pytest.mark.asyncio
async def test_round_trip_multiple_frames() -> None:
    frames = [b"one", b"two", b"three"]
    stream = b"".join(encode_frame(f) for f in frames)
    reader = _BufferReader(stream)
    decoded = [await decode_frame(reader.read_exactly) for _ in frames]
    assert decoded == frames


@pytest.mark.asyncio
async def test_empty_payload_is_a_valid_frame() -> None:
    reader = _BufferReader(encode_frame(b""))
    assert await decode_frame(reader.read_exactly) == b""


@pytest.mark.asyncio
async def test_clean_eof_at_frame_boundary_returns_none() -> None:
    reader = _BufferReader(b"")
    assert await decode_frame(reader.read_exactly) is None


@pytest.mark.asyncio
async def test_eof_mid_header_raises_incomplete_frame() -> None:
    reader = _BufferReader(b"\x00\x00")  # only 2 of 4 header bytes
    with pytest.raises(IncompleteFrame):
        await decode_frame(reader.read_exactly)


@pytest.mark.asyncio
async def test_eof_mid_payload_raises_incomplete_frame() -> None:
    full = encode_frame(b"hello world")
    truncated = full[:-3]  # header claims 11 bytes, only 8 delivered
    reader = _BufferReader(truncated)
    with pytest.raises(IncompleteFrame):
        await decode_frame(reader.read_exactly)


def test_encode_rejects_oversized_payload() -> None:
    with pytest.raises(ValueError):
        encode_frame(b"x" * (MAX_FRAME_BYTES + 1))


@pytest.mark.asyncio
async def test_decode_rejects_oversized_declared_length() -> None:
    bad_header = struct.pack(">I", MAX_FRAME_BYTES + 1)
    reader = _BufferReader(bad_header)
    with pytest.raises(ValueError):
        await decode_frame(reader.read_exactly)
