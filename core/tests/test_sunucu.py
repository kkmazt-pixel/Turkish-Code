"""Integration tests for :class:`AsyncCoreChannel` over real OS pipes (doc 10).

Uses genuine ``os.pipe()`` transports (``tests/pipes.py``) rather than mocks,
so these exercise the real asyncio read/write loop, not a stand-in for it.
"""

from __future__ import annotations

import asyncio

import pytest
from turkish_code.kanal.dagitim import DEADLINE_EXCEEDED_CODE
from turkish_code.kanal.mesaj import (
    ErrorResponse,
    Notification,
    Request,
    SuccessResponse,
)
from turkish_code.kanal.sunucu import AsyncCoreChannel

from tests.pipes import real_transport_pair


async def _echo(request: Request) -> SuccessResponse:
    return SuccessResponse(id=request.id, result={"method": request.method})


@pytest.mark.asyncio
async def test_request_response_round_trip_over_real_pipes() -> None:
    server_transport, client_transport = await real_transport_pair()
    server = AsyncCoreChannel(server_transport)
    client = AsyncCoreChannel(client_transport)
    server.register("app.ping", _echo)

    server_task = asyncio.ensure_future(server.serve())
    client_task = asyncio.ensure_future(client.serve())
    try:
        response = await client.request("app.ping")
        assert isinstance(response, SuccessResponse)
        assert response.result == {"method": "app.ping"}
    finally:
        server.request_shutdown()
        client.request_shutdown()
        await server_task
        await client_task
        await server.aclose()
        await client.aclose()


@pytest.mark.asyncio
async def test_concurrent_requests_are_not_head_of_line_blocked() -> None:
    order: list[str] = []

    async def _slow(request: Request) -> SuccessResponse:
        await asyncio.sleep(0.05)
        order.append("slow")
        return SuccessResponse(id=request.id, result="slow")

    async def _fast(request: Request) -> SuccessResponse:
        order.append("fast")
        return SuccessResponse(id=request.id, result="fast")

    server_transport, client_transport = await real_transport_pair()
    server = AsyncCoreChannel(server_transport)
    client = AsyncCoreChannel(client_transport)
    server.register("slow", _slow)
    server.register("fast", _fast)

    server_task = asyncio.ensure_future(server.serve())
    client_task = asyncio.ensure_future(client.serve())
    try:
        slow_response, fast_response = await asyncio.gather(
            client.request("slow"), client.request("fast")
        )
        assert isinstance(slow_response, SuccessResponse)
        assert isinstance(fast_response, SuccessResponse)
        assert order == ["fast", "slow"]
    finally:
        server.request_shutdown()
        client.request_shutdown()
        await server_task
        await client_task
        await server.aclose()
        await client.aclose()


@pytest.mark.asyncio
async def test_deadline_exceeded_yields_typed_error_response() -> None:
    async def _slow(request: Request) -> SuccessResponse:
        await asyncio.sleep(10)
        return SuccessResponse(id=request.id, result=None)

    server_transport, client_transport = await real_transport_pair()
    server = AsyncCoreChannel(server_transport)
    client = AsyncCoreChannel(client_transport)
    server.register("slow", _slow)

    server_task = asyncio.ensure_future(server.serve())
    client_task = asyncio.ensure_future(client.serve())
    try:
        response = await client.request("slow", meta={"deadlineMs": 5})
        assert isinstance(response, ErrorResponse)
        assert response.error.data is not None
        assert response.error.data["code"] == DEADLINE_EXCEEDED_CODE
    finally:
        server.request_shutdown()
        client.request_shutdown()
        await server_task
        await client_task
        await server.aclose()
        await client.aclose()


@pytest.mark.asyncio
async def test_cancel_notification_stops_a_registered_run() -> None:
    cancelled = asyncio.Event()

    async def _long_task(request: Request) -> SuccessResponse:
        token = server.register_run("run-1")
        await token.wait()
        cancelled.set()
        return SuccessResponse(id=request.id, result="cancelled")

    server_transport, client_transport = await real_transport_pair()
    server = AsyncCoreChannel(server_transport)
    client = AsyncCoreChannel(client_transport)
    server.register("run.long", _long_task)

    server_task = asyncio.ensure_future(server.serve())
    client_task = asyncio.ensure_future(client.serve())
    try:
        request_future = asyncio.ensure_future(client.request("run.long"))
        await asyncio.sleep(0.01)  # let the handler register its run
        client.notify(Notification(method="$/cancel", params={"runId": "run-1"}))

        response = await asyncio.wait_for(request_future, timeout=2)
        assert isinstance(response, SuccessResponse)
        assert cancelled.is_set()
    finally:
        server.request_shutdown()
        client.request_shutdown()
        await server_task
        await client_task
        await server.aclose()
        await client.aclose()


@pytest.mark.asyncio
async def test_malformed_frame_is_dropped_without_crashing_the_loop() -> None:
    server_transport, client_transport = await real_transport_pair()
    server = AsyncCoreChannel(server_transport)
    server.register("app.ping", _echo)

    server_task = asyncio.ensure_future(server.serve())
    try:
        await client_transport.write_frame(b"not valid json-rpc")
        # The malformed frame is silently dropped (doc 10 §14, no response sent);
        # confirm the server loop is still alive by sending a real request after.
        request = Request(id=1, method="app.ping")
        await client_transport.write_frame(_encode(request))
        response = await client_transport.read_frame()
        assert response is not None
    finally:
        server.request_shutdown()
        await server_task
        await server.aclose()
        await client_transport.aclose()


@pytest.mark.asyncio
async def test_serve_returns_on_clean_transport_eof() -> None:
    server_transport, client_transport = await real_transport_pair()
    server = AsyncCoreChannel(server_transport)

    server_task = asyncio.ensure_future(server.serve())
    await client_transport.aclose()

    await asyncio.wait_for(server_task, timeout=2)
    await server.aclose()


def _encode(request: Request) -> bytes:
    import json

    return json.dumps(request.to_wire()).encode("utf-8")
