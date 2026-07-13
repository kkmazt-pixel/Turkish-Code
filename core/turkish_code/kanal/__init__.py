"""Core Channel subsystem (doc 10) — the stdio JSON-RPC 2.0 runtime.

Message value types, length-prefixed framing, transport I/O, structural
validation, cooperative cancellation, request correlation, and dispatch —
composed into the concrete :class:`~turkish_code.kanal.sunucu.AsyncCoreChannel`.
"""

from turkish_code.kanal.aktarim import StdioTransport, Transport
from turkish_code.kanal.cerceve import (
    HEADER_SIZE,
    MAX_FRAME_BYTES,
    IncompleteFrame,
    decode_frame,
    encode_frame,
)
from turkish_code.kanal.dagitim import (
    CANCEL_METHOD,
    DEADLINE_EXCEEDED_CODE,
    INTERNAL_ERROR_CODE,
    METHOD_NOT_FOUND_CODE,
    Handler,
    NotificationHandler,
    dispatch_notification,
    dispatch_request,
)
from turkish_code.kanal.dogrulama import (
    MALFORMED_FRAME_CODE,
    ParsedMessage,
    parse_frame,
)
from turkish_code.kanal.eslesme import PendingRequests
from turkish_code.kanal.iptal import CancellationRegistry, CancellationToken
from turkish_code.kanal.mesaj import (
    ErrorResponse,
    JsonRpcError,
    Notification,
    Request,
    Response,
    SuccessResponse,
    code_for_kind,
    error_response_from_app_error,
)
from turkish_code.kanal.sunucu import AsyncCoreChannel, CoreChannel

__all__ = [
    "Request",
    "Notification",
    "SuccessResponse",
    "ErrorResponse",
    "JsonRpcError",
    "code_for_kind",
    "error_response_from_app_error",
    "CoreChannel",
    "AsyncCoreChannel",
    "Handler",
    "NotificationHandler",
    "Response",
    "Transport",
    "StdioTransport",
    "HEADER_SIZE",
    "MAX_FRAME_BYTES",
    "IncompleteFrame",
    "encode_frame",
    "decode_frame",
    "MALFORMED_FRAME_CODE",
    "ParsedMessage",
    "parse_frame",
    "CancellationToken",
    "CancellationRegistry",
    "PendingRequests",
    "CANCEL_METHOD",
    "METHOD_NOT_FOUND_CODE",
    "DEADLINE_EXCEEDED_CODE",
    "INTERNAL_ERROR_CODE",
    "dispatch_request",
    "dispatch_notification",
]
