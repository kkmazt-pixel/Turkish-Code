"""Transport over framed bytes (doc 09 §5/§6, doc 10 §6.1).

``Transport`` is the only boundary that does real I/O. :class:`StdioTransport`
takes already-connected ``asyncio`` streams rather than reaching for
``sys.stdin``/``sys.stdout`` itself — so it is fully unit-testable with any
reader/writer pair (real ``os.pipe()`` included), and the one place that binds
those streams to the *actual* process stdio is :func:`open_stdio_streams`,
called only from the sidecar entrypoint.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Protocol, runtime_checkable

from turkish_code.kanal.cerceve import IncompleteFrame, decode_frame, encode_frame


@runtime_checkable
class Transport(Protocol):
    """A framed-byte channel (doc 10 §6.1) — the sole stdout writer (doc 09 §6)."""

    async def read_frame(self) -> bytes | None:
        """Read the next frame, or ``None`` on clean EOF (doc 10 §17)."""
        ...

    async def write_frame(self, payload: bytes) -> None:
        """Write one frame."""
        ...

    async def aclose(self) -> None:
        """Close the underlying streams."""
        ...


class StdioTransport:
    """A :class:`Transport` over an injected pair of asyncio streams."""

    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self._reader = reader
        self._writer = writer

    async def read_frame(self) -> bytes | None:
        return await decode_frame(self._read_exactly)

    async def _read_exactly(self, n: int) -> bytes:
        try:
            return await self._reader.readexactly(n)
        except asyncio.IncompleteReadError as exc:
            raise IncompleteFrame(expected=n, partial=exc.partial) from exc

    async def write_frame(self, payload: bytes) -> None:
        self._writer.write(encode_frame(payload))
        await self._writer.drain()

    async def aclose(self) -> None:
        self._writer.close()
        await self._writer.wait_closed()


async def open_stdio_streams() -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Bind real process stdin/stdout to asyncio streams (doc 09 §5).

    The only function in this module touching the real process fds; called
    once from ``__main__.py``. stdin/stdout here are the Kabuk-owned pipes
    (doc 08 §9), not a console, so pipe transports apply on every platform.
    """
    loop = asyncio.get_running_loop()

    reader = asyncio.StreamReader()
    reader_protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: reader_protocol, sys.stdin)

    writer = await connect_write_pipe(sys.stdout)
    return reader, writer


class _StdoutGuard:
    """Raises on any write to stdout after boot (doc 09 §16).

    stdout is reserved exclusively for the Core Channel's framed protocol
    bytes; a stray ``print()`` or library banner would corrupt the wire.
    """

    def write(self, data: str) -> int:
        if data:
            raise RuntimeError(
                "stdout is reserved for the Core Channel protocol (doc 09 §16); "
                "route logging to stderr instead"
            )
        return 0

    def flush(self) -> None:
        return None


def guard_stdout() -> None:
    """Replace ``sys.stdout`` with a guard that raises on any write (doc 09 §16).

    Call once, at boot, before constructing anything that might accidentally
    ``print()``. Safe: the real protocol writer never goes through
    ``sys.stdout`` — it binds the raw fd directly via :func:`connect_write_pipe`.
    """
    sys.stdout = _StdoutGuard()


async def connect_write_pipe(pipe: object) -> asyncio.StreamWriter:
    """Wrap a write-only pipe as a :class:`asyncio.StreamWriter`.

    Paired with :class:`asyncio.StreamReaderProtocol` (not the bare
    ``FlowControlMixin``) because ``StreamWriter.wait_closed()`` calls
    ``protocol._get_close_waiter()``, which only ``StreamReaderProtocol``
    implements — the reader it wraps is never used for a write-only pipe.
    """
    loop = asyncio.get_running_loop()
    protocol = asyncio.StreamReaderProtocol(asyncio.StreamReader(), loop=loop)
    transport, _ = await loop.connect_write_pipe(lambda: protocol, pipe)
    return asyncio.StreamWriter(transport, protocol, None, loop)
