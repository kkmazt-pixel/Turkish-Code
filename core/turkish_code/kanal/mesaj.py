"""JSON-RPC 2.0 message value types for the Core Channel (doc 10 §7/§14).

These immutable envelopes are the wire contract between Kabuk and Çekirdek. The
concrete transport (length-prefixed stdio) belongs to a later increment; here we
define the message shapes and the mapping from a typed :class:`AppError` to a
JSON-RPC error object (doc 38 §6).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, assert_never

from turkish_code.hata import AppError, ErrorKind

JSONRPC_VERSION = "2.0"

RequestId = int | str


def code_for_kind(kind: ErrorKind) -> int:
    """Return the stable JSON-RPC numeric code for a typed error kind (doc 10 §14).

    Typed errors map to the JSON-RPC "server error" band (-32000..-32099), which
    the spec reserves for implementation-defined codes. Timeout is pinned to
    -32050 by doc 38 §19; the remaining kinds fill the band deterministically so
    the numeric code is a stable part of the contract.

    Exhaustiveness is enforced at type-check time: adding an ``ErrorKind`` without
    a case here makes ``assert_never`` a mypy error (no bare ``KeyError`` at
    runtime, unlike a dict lookup — doc 36 §5.3 / doc 38 §7).
    """
    match kind:
        case ErrorKind.INTERNAL:
            return -32000
        case ErrorKind.VALIDATION:
            return -32040
        case ErrorKind.PERMISSION:
            return -32041
        case ErrorKind.NOT_FOUND:
            return -32042
        case ErrorKind.CONFLICT:
            return -32043
        case ErrorKind.PROVIDER:
            return -32044
        case ErrorKind.EGRESS:
            return -32045
        case ErrorKind.RESOURCE:
            return -32046
        case ErrorKind.BUDGET:
            return -32047
        case ErrorKind.CANCELLED:
            return -32048
        case ErrorKind.CORRUPTION:
            return -32049
        case ErrorKind.TIMEOUT:
            return -32050
        case ErrorKind.SECURITY:
            return -32051
    assert_never(kind)


@dataclass(frozen=True, slots=True)
class Request:
    """A JSON-RPC request expecting a correlated response (doc 10 §7)."""

    id: RequestId
    method: str
    params: Mapping[str, Any] | None = None

    def to_wire(self) -> dict[str, Any]:
        """Serialize to the JSON-RPC request envelope."""
        wire: dict[str, Any] = {
            "jsonrpc": JSONRPC_VERSION,
            "id": self.id,
            "method": self.method,
        }
        if self.params is not None:
            wire["params"] = dict(self.params)
        return wire


@dataclass(frozen=True, slots=True)
class Notification:
    """A JSON-RPC notification: no id, no response (doc 10)."""

    method: str
    params: Mapping[str, Any] | None = None

    def to_wire(self) -> dict[str, Any]:
        """Serialize to the JSON-RPC notification envelope."""
        wire: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": self.method}
        if self.params is not None:
            wire["params"] = dict(self.params)
        return wire


@dataclass(frozen=True, slots=True)
class JsonRpcError:
    """The ``error`` member of a JSON-RPC error response (doc 10 §14)."""

    code: int
    message: str
    data: Mapping[str, Any] | None = None

    def to_wire(self) -> dict[str, Any]:
        wire: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            wire["data"] = dict(self.data)
        return wire


@dataclass(frozen=True, slots=True)
class SuccessResponse:
    """A successful JSON-RPC response correlated by ``id`` (doc 10 §7)."""

    id: RequestId
    result: Any

    def to_wire(self) -> dict[str, Any]:
        return {"jsonrpc": JSONRPC_VERSION, "id": self.id, "result": self.result}


@dataclass(frozen=True, slots=True)
class ErrorResponse:
    """A failed JSON-RPC response carrying a typed error payload (doc 10 §14)."""

    id: RequestId | None
    error: JsonRpcError

    def to_wire(self) -> dict[str, Any]:
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": self.id,
            "error": self.error.to_wire(),
        }


def error_response_from_app_error(
    request_id: RequestId | None, err: AppError
) -> ErrorResponse:
    """Map a typed :class:`AppError` to a JSON-RPC error response (doc 38 §6).

    ``error.data`` carries the caller-actionable payload (kind/code/retryable/…);
    ``message`` is the i18n key, localized UI-side (the Çekirdek does not localize).
    Log-only fields (``detail``, cause chain) are excluded by ``to_error_data``.
    """
    return ErrorResponse(
        id=request_id,
        error=JsonRpcError(
            code=code_for_kind(err.kind),
            message=err.message_key,
            data=err.to_error_data(),
        ),
    )
