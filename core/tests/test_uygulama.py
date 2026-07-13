"""Tests for the ``app.*`` handlers (doc 10 §13/§67)."""

from __future__ import annotations

import datetime

import pytest
from turkish_code.hata import AppError
from turkish_code.kanal.dagitim import Handler
from turkish_code.kanal.mesaj import PROTOCOL_VERSION, Request, SuccessResponse
from turkish_code.kanal.uygulama import (
    INCOMPATIBLE_PROTOCOL_CODE,
    register_app_handlers,
)
from turkish_code.ortak.saat import Clock
from turkish_code.saglayicilar.cache import InMemoryModelCache
from turkish_code.saglayicilar.manager import ProviderManager
from turkish_code.saglayicilar.provider import HealthStatus

from tests.fakes import StubProvider


class _FixedClock:
    def now(self) -> datetime.datetime:
        return datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _manager(*providers: StubProvider) -> ProviderManager:
    clock: Clock = _FixedClock()
    return ProviderManager(list(providers), cache=InMemoryModelCache(), clock=clock)


def _handlers(
    *, provider_manager: ProviderManager, session_token: str = "tok-1"
) -> tuple[dict[str, Handler], list[str]]:
    handlers: dict[str, Handler] = {}
    shutdown_calls: list[str] = []

    register_app_handlers(
        register=lambda method, handler: handlers.__setitem__(method, handler),
        core_version="0.0.0",
        session_token=session_token,
        provider_manager=provider_manager,
        on_shutdown=lambda: shutdown_calls.append("shutdown"),
    )
    return handlers, shutdown_calls


@pytest.mark.asyncio
async def test_handshake_reports_version_and_providers() -> None:
    manager = _manager(StubProvider("gemini"), StubProvider("ollama"))
    handlers, _ = _handlers(provider_manager=manager)

    response = await handlers["app.handshake"](Request(id=1, method="app.handshake"))

    assert isinstance(response, SuccessResponse)
    assert response.result["protocolVersion"] == PROTOCOL_VERSION
    assert response.result["coreVersion"] == "0.0.0"
    assert response.result["authToken"] == "tok-1"
    assert set(response.result["providers"]) == {"gemini", "ollama"}


@pytest.mark.asyncio
async def test_handshake_accepts_compatible_major_version() -> None:
    handlers, _ = _handlers(provider_manager=_manager())
    request = Request(id=1, method="app.handshake", params={"protocolVersion": "1.9.9"})
    response = await handlers["app.handshake"](request)
    assert isinstance(response, SuccessResponse)


@pytest.mark.asyncio
async def test_handshake_rejects_incompatible_major_version() -> None:
    handlers, _ = _handlers(provider_manager=_manager())
    request = Request(id=1, method="app.handshake", params={"protocolVersion": "2.0.0"})
    with pytest.raises(AppError) as exc_info:
        await handlers["app.handshake"](request)
    assert exc_info.value.code == INCOMPATIBLE_PROTOCOL_CODE


@pytest.mark.asyncio
async def test_handshake_ignores_missing_peer_version() -> None:
    handlers, _ = _handlers(provider_manager=_manager())
    response = await handlers["app.handshake"](Request(id=1, method="app.handshake"))
    assert isinstance(response, SuccessResponse)


@pytest.mark.asyncio
async def test_health_reports_provider_status() -> None:
    manager = _manager(StubProvider("gemini", health=HealthStatus.DOWN))
    handlers, _ = _handlers(provider_manager=manager)

    response = await handlers["app.health"](Request(id=1, method="app.health"))

    assert isinstance(response, SuccessResponse)
    assert response.result == {"gemini": "down"}


@pytest.mark.asyncio
async def test_shutdown_acknowledges_and_signals_callback() -> None:
    handlers, shutdown_calls = _handlers(provider_manager=_manager())

    response = await handlers["app.shutdown"](Request(id=1, method="app.shutdown"))

    assert isinstance(response, SuccessResponse)
    assert response.result == {"acknowledged": True}
    assert shutdown_calls == ["shutdown"]
