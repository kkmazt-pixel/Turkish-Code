"""A real, full-duplex ``StdioTransport`` pair over two OS pipes.

Used to test the Core Channel over genuine OS-level I/O (not mocked) without
spawning a real subprocess — one pipe per direction, wired into two
:class:`~turkish_code.kanal.aktarim.StdioTransport` instances that talk to
each other exactly as Kabuk<->Çekirdek would. Each of the four pipe fds is
connected to exactly one asyncio protocol (double-connecting a single fd is
undefined behavior).
"""

from __future__ import annotations

import asyncio
import os

from turkish_code.kanal.aktarim import StdioTransport, connect_write_pipe


async def _reader_for(read_fd: int) -> asyncio.StreamReader:
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, os.fdopen(read_fd, "rb"))
    return reader


async def _writer_for(write_fd: int) -> asyncio.StreamWriter:
    return await connect_write_pipe(os.fdopen(write_fd, "wb"))


async def real_transport_pair() -> tuple[StdioTransport, StdioTransport]:
    """Two connected transports over real OS pipes: ``a``'s writes reach
    ``b``'s reads, and ``b``'s writes reach ``a``'s reads."""
    a_to_b_read, a_to_b_write = os.pipe()
    b_to_a_read, b_to_a_write = os.pipe()

    a = StdioTransport(await _reader_for(b_to_a_read), await _writer_for(a_to_b_write))
    b = StdioTransport(await _reader_for(a_to_b_read), await _writer_for(b_to_a_write))
    return a, b
