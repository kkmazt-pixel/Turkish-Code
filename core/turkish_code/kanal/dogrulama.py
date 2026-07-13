"""Frame validation: raw bytes → typed JSON-RPC message (doc 10 §17, doc 38).

Structural validation only — malformed JSON, wrong ``jsonrpc`` version, or a
shape matching no known message type is rejected here as a typed
``Validation`` error, never a crash (doc 36 §3). Whether a *method* is known
is the dispatcher's job (it owns the handler registry, doc 09 §8), not this
module's — this only checks the JSON-RPC envelope shape.
"""

from __future__ import annotations

import json
from typing import Any

from turkish_code.hata import AppError, ErrorKind
from turkish_code.kanal.mesaj import (
    JSONRPC_VERSION,
    ErrorResponse,
    JsonRpcError,
    Notification,
    Request,
    SuccessResponse,
)

ParsedMessage = Request | Notification | SuccessResponse | ErrorResponse

MALFORMED_FRAME_CODE = "ipc.malformed_frame"


def parse_frame(raw: bytes) -> ParsedMessage:
    """Parse one frame payload into a typed message (doc 10 §6.2).

    Raises:
        AppError: ``Validation`` kind if the bytes aren't valid UTF-8/JSON,
            aren't a JSON object, use an unsupported ``jsonrpc`` version, or
            match no known request/notification/response shape.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _malformed(f"invalid UTF-8 in frame: {exc}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _malformed(f"invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise _malformed("frame is not a JSON object")
    if data.get("jsonrpc") != JSONRPC_VERSION:
        raise _malformed(f"unsupported jsonrpc version: {data.get('jsonrpc')!r}")

    return _classify(data)


def _classify(data: dict[str, Any]) -> ParsedMessage:
    has_id = "id" in data

    if "method" in data:
        method = data["method"]
        if not isinstance(method, str):
            raise _malformed("method must be a string")
        params = data.get("params")
        if has_id:
            return Request(
                id=data["id"], method=method, params=params, meta=data.get("meta")
            )
        return Notification(method=method, params=params)

    if "result" in data and has_id:
        return SuccessResponse(id=data["id"], result=data["result"])

    if "error" in data:
        return ErrorResponse(id=data.get("id"), error=_parse_error(data["error"]))

    raise _malformed("frame matches no known JSON-RPC message shape")


def _parse_error(error: object) -> JsonRpcError:
    if not isinstance(error, dict) or "code" not in error or "message" not in error:
        raise _malformed("malformed error object")
    return JsonRpcError(
        code=error["code"], message=error["message"], data=error.get("data")
    )


def _malformed(detail: str) -> AppError:
    return AppError(
        kind=ErrorKind.VALIDATION,
        code=MALFORMED_FRAME_CODE,
        message_key="hata.ipc.malformed_frame",
        retryable=False,
        detail=detail,
    )
