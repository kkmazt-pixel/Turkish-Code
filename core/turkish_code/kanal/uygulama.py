"""``app.*`` handlers (doc 10 §13/§67) — handshake, health, shutdown.

The Kabuk drives this side of the protocol; the Çekirdek only answers. These
handlers are pure request/response — they know nothing about the transport or
dispatch loop, only the object graph they're constructed with (doc 09 §7).
"""

from __future__ import annotations

from collections.abc import Callable

from turkish_code.hata import AppError, ErrorKind
from turkish_code.kanal.dagitim import Handler
from turkish_code.kanal.mesaj import PROTOCOL_VERSION, Request, SuccessResponse
from turkish_code.saglayicilar.manager import ProviderManager

INCOMPATIBLE_PROTOCOL_CODE = "ipc.incompatible_protocol_version"


def register_app_handlers(
    *,
    register: Callable[[str, Handler], None],
    core_version: str,
    session_token: str,
    provider_manager: ProviderManager,
    on_shutdown: Callable[[], None],
) -> None:
    """Bind ``app.handshake``/``app.health``/``app.shutdown`` (doc 10 §67).

    ``on_shutdown`` decouples this module from any concrete channel type
    (Protocol-first, doc 36 §5.3) — it's called to signal ``serve()`` to
    return once the shutdown response has been sent.
    """
    register(
        "app.handshake",
        _handshake_handler(core_version, session_token, provider_manager),
    )
    register("app.health", _health_handler(provider_manager))
    register("app.shutdown", _shutdown_handler(on_shutdown))


def _handshake_handler(
    core_version: str, session_token: str, provider_manager: ProviderManager
) -> Handler:
    async def _handle(request: Request) -> SuccessResponse:
        _check_compatibility(request)
        return SuccessResponse(
            id=request.id,
            result={
                "protocolVersion": PROTOCOL_VERSION,
                "coreVersion": core_version,
                "capabilities": [],
                "providers": list(provider_manager.provider_ids()),
                "models": [],
                "authToken": session_token,
            },
        )

    return _handle


def _health_handler(provider_manager: ProviderManager) -> Handler:
    async def _handle(request: Request) -> SuccessResponse:
        snapshot = await provider_manager.health_snapshot()
        return SuccessResponse(
            id=request.id,
            result={
                provider_id: status.value for provider_id, status in snapshot.items()
            },
        )

    return _handle


def _shutdown_handler(on_shutdown: Callable[[], None]) -> Handler:
    async def _handle(request: Request) -> SuccessResponse:
        response = SuccessResponse(id=request.id, result={"acknowledged": True})
        on_shutdown()
        return response

    return _handle


def _check_compatibility(request: Request) -> None:
    """Reject a handshake from an incompatible major protocol version (doc 10 §13)."""
    params = request.params or {}
    peer_version = params.get("protocolVersion")
    if not isinstance(peer_version, str):
        return
    if _major(peer_version) != _major(PROTOCOL_VERSION):
        raise AppError(
            kind=ErrorKind.VALIDATION,
            code=INCOMPATIBLE_PROTOCOL_CODE,
            message_key="hata.ipc.incompatible_protocol_version",
            retryable=False,
            context={"ours": PROTOCOL_VERSION, "theirs": peer_version},
        )


def _major(version: str) -> str:
    return version.split(".", 1)[0]
