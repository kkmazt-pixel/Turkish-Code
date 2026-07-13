"""Çekirdek sidecar entrypoint (doc 09 §5) — the Kabuk-spawned process.

Guards stdout (doc 09 §16), builds the DI container (doc 09 §7), binds the
real process stdio to the Core Channel, wires the ``app.*`` handlers, and
serves until ``app.shutdown`` or a clean EOF on stdin (doc 10 §17).
"""

from __future__ import annotations

import asyncio
import os

from turkish_code.kanal.aktarim import StdioTransport, guard_stdout, open_stdio_streams
from turkish_code.kompozisyon import build_channel, build_container
from turkish_code.yapilandirma.sabitler import ENV_CORE_SESSION_TOKEN
from turkish_code.yapilandirma.yukleyici import load_settings


async def _run() -> None:
    settings = load_settings(os.environ)
    container = build_container(settings)

    reader, writer = await open_stdio_streams()
    transport = StdioTransport(reader, writer)
    channel = build_channel(
        container,
        transport,
        session_token=os.environ.get(ENV_CORE_SESSION_TOKEN, ""),
    )

    try:
        await channel.serve()
    finally:
        await channel.aclose()


def main() -> None:
    """Synchronous process entrypoint (``python -m turkish_code``)."""
    guard_stdout()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
