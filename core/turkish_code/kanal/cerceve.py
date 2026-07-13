"""Length-prefixed frame codec (doc 10 §6.1) — pure, no I/O.

A 4-byte big-endian unsigned length header followed by that many bytes of
UTF-8 JSON. One message = one frame. Chosen over newline-delimited JSON
because payloads may contain newlines (doc 10 §6.1) — length-prefixing is
unambiguous and streamable.
"""

from __future__ import annotations

import struct
from collections.abc import Awaitable, Callable

HEADER_SIZE = 4
MAX_FRAME_BYTES = 64 * 1024 * 1024
"""Bounds a single control/stream frame (PR-14); anything larger belongs on
the bulk plane (doc 10 §11), never inlined here."""

ReadExactly = Callable[[int], Awaitable[bytes]]
"""Reads exactly ``n`` bytes, or raises :class:`IncompleteFrame` if the
stream ends first — the contract a transport's reader must satisfy."""


class IncompleteFrame(Exception):
    """The stream ended before the requested bytes arrived (doc 10 §17).

    ``partial`` carries whatever bytes were read before the stream closed —
    empty when the stream closed cleanly at a frame boundary.
    """

    def __init__(self, expected: int, partial: bytes) -> None:
        super().__init__(f"expected {expected} bytes, got {len(partial)}")
        self.expected = expected
        self.partial = partial


def encode_frame(payload: bytes) -> bytes:
    """Prefix ``payload`` with its 4-byte big-endian length (doc 10 §6.1)."""
    if len(payload) > MAX_FRAME_BYTES:
        raise ValueError(
            f"frame payload of {len(payload)} bytes exceeds max {MAX_FRAME_BYTES}"
        )
    return struct.pack(">I", len(payload)) + payload


async def decode_frame(read_exactly: ReadExactly) -> bytes | None:
    """Read one frame via ``read_exactly`` (doc 10 §6.1).

    Returns ``None`` on a clean EOF at a frame boundary (no header bytes at
    all); an EOF *inside* a header or payload is a protocol desync and
    propagates as :class:`IncompleteFrame` (doc 10 §17 "pipe closed
    unexpectedly").
    """
    try:
        header = await read_exactly(HEADER_SIZE)
    except IncompleteFrame as exc:
        if len(exc.partial) == 0:
            return None
        raise

    (length,) = struct.unpack(">I", header)
    if length > MAX_FRAME_BYTES:
        raise ValueError(f"frame length {length} exceeds max {MAX_FRAME_BYTES}")
    return await read_exactly(length)
