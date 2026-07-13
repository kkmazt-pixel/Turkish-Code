"""Core Channel subsystem (doc 10) — contract skeleton.

Defines the JSON-RPC 2.0 message value types and the server abstraction that
subsystems register handlers on. The concrete stdio framing/dispatch loop is a
later increment (doc 42 walking skeleton); this module is the seam, not the I/O.
"""

from turkish_code.kanal.mesaj import (
    ErrorResponse,
    JsonRpcError,
    Notification,
    Request,
    SuccessResponse,
    code_for_kind,
    error_response_from_app_error,
)
from turkish_code.kanal.sunucu import CoreChannel, Handler, Response

__all__ = [
    "Request",
    "Notification",
    "SuccessResponse",
    "ErrorResponse",
    "JsonRpcError",
    "code_for_kind",
    "error_response_from_app_error",
    "CoreChannel",
    "Handler",
    "Response",
]
