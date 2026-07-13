"""Tests for the Core Channel message contract and error mapping (doc 10 §14)."""

from __future__ import annotations

from turkish_code.hata import AppError, ErrorKind
from turkish_code.kanal.dagitim import Handler
from turkish_code.kanal.mesaj import (
    JSONRPC_VERSION,
    Notification,
    Request,
    Response,
    SuccessResponse,
    code_for_kind,
    error_response_from_app_error,
)
from turkish_code.kanal.sunucu import CoreChannel


def test_request_wire_omits_absent_params() -> None:
    assert Request(id=1, method="app.ping").to_wire() == {
        "jsonrpc": JSONRPC_VERSION,
        "id": 1,
        "method": "app.ping",
    }


def test_request_wire_includes_params() -> None:
    wire = Request(id="a", method="memory.recall", params={"q": "x"}).to_wire()
    assert wire["params"] == {"q": "x"}


def test_notification_has_no_id() -> None:
    wire = Notification(method="run.step").to_wire()
    assert "id" not in wire
    assert wire["method"] == "run.step"


def test_success_response_wire() -> None:
    assert SuccessResponse(id=7, result={"ok": True}).to_wire() == {
        "jsonrpc": JSONRPC_VERSION,
        "id": 7,
        "result": {"ok": True},
    }


def test_code_for_kind_is_exhaustive_and_in_server_band() -> None:
    for kind in ErrorKind:
        code = code_for_kind(kind)  # must not raise for any kind
        assert -32099 <= code <= -32000


def test_timeout_code_matches_doc_38() -> None:
    assert code_for_kind(ErrorKind.TIMEOUT) == -32050


def test_kind_codes_are_unique() -> None:
    """A3: each kind maps to a distinct wire code (no collisions in the band)."""
    codes = [code_for_kind(kind) for kind in ErrorKind]
    assert len(set(codes)) == len(codes)


def test_error_response_from_app_error_maps_payload() -> None:
    err = AppError(
        kind=ErrorKind.TIMEOUT,
        code="provider.timeout",
        message_key="hata.provider.timeout",
        retryable=True,
        remedy_key="caba.hizli_dene",
        detail="socket read timed out",  # log-only, must not surface
    )
    response = error_response_from_app_error(request_id=42, err=err)
    wire = response.to_wire()

    assert wire["id"] == 42
    assert wire["error"]["code"] == -32050
    assert wire["error"]["message"] == "hata.provider.timeout"
    assert wire["error"]["data"] == err.to_error_data()
    assert "detail" not in wire["error"]["data"]
    assert "socket read" not in str(wire)


def test_core_channel_protocol_is_implementable() -> None:
    """A minimal fake proves the server abstraction is coherent (doc 10)."""

    class FakeChannel:
        def __init__(self) -> None:
            self.methods: dict[str, Handler] = {}

        def register(self, method: str, handler: Handler) -> None:
            self.methods[method] = handler

        def notify(self, note: Notification) -> None:
            return None

        async def serve(self) -> None:
            return None

    fake = FakeChannel()
    assert isinstance(fake, CoreChannel)

    async def handler(_: Request) -> Response:
        return SuccessResponse(id=1, result=None)

    fake.register("app.ping", handler)
    assert "app.ping" in fake.methods
