"""Tool-runtime failures as typed :class:`AppError` values (doc 20 §15, doc 38).

The tool runtime never lets a raw exception escape a call: a missing tool is a
``NOT_FOUND``, malformed args are a ``VALIDATION`` error, a permission refusal is
``PERMISSION``, a deadline is ``TIMEOUT``, cooperative cancellation is
``CANCELLED``, and an unexpected failure inside a tool is ``INTERNAL`` (doc 38
§4/§7). The reasoning loop observes the typed error and adapts — retry,
alternative, or ask (doc 20 §15, PR-7/PR-10). Codes are stable machine strings
(doc 38 §23); renaming one is a migration.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from turkish_code.araclar.modeller import Capability
from turkish_code.hata import AppError, ErrorKind

TOOL_NOT_FOUND_CODE = "tool.not_found"
TOOL_INVALID_ARGS_CODE = "tool.invalid_args"
TOOL_DENIED_CODE = "tool.denied"
TOOL_TIMEOUT_CODE = "tool.timeout"
TOOL_CANCELLED_CODE = "tool.cancelled"
TOOL_FAILED_CODE = "tool.failed"
TOOL_DUPLICATE_CODE = "tool.duplicate"


def tool_not_found(name: str) -> AppError:
    """No tool is registered under ``name`` (doc 20 §11)."""
    return _tool_error(
        ErrorKind.NOT_FOUND,
        TOOL_NOT_FOUND_CODE,
        retryable=False,
        detail=f"no tool registered as {name!r}",
        context={"tool": name},
    )


def invalid_tool_args(name: str, detail: str) -> AppError:
    """The call arguments failed validation before execution (doc 20 §8)."""
    return _tool_error(
        ErrorKind.VALIDATION,
        TOOL_INVALID_ARGS_CODE,
        retryable=False,
        detail=f"invalid args for {name!r}: {detail}",
        context={"tool": name},
    )


def tool_denied(name: str, capability: Capability | None) -> AppError:
    """The permission engine denied the required capability (doc 24 §6)."""
    return _tool_error(
        ErrorKind.PERMISSION,
        TOOL_DENIED_CODE,
        retryable=False,
        detail=f"permission denied for {name!r} ({capability})",
        context={"tool": name, "capability": capability},
    )


def tool_timeout(name: str, timeout_ms: int) -> AppError:
    """Execution exceeded the tool's deadline (doc 20 §9/§14)."""
    return _tool_error(
        ErrorKind.TIMEOUT,
        TOOL_TIMEOUT_CODE,
        retryable=True,
        detail=f"{name!r} exceeded {timeout_ms}ms",
        context={"tool": name, "timeoutMs": timeout_ms},
    )


def tool_cancelled(name: str) -> AppError:
    """The call was cooperatively cancelled (doc 10 §10, doc 20 §11).

    Cancellation is a user action, not an error state (doc 10 §10); it is still
    a typed value so the runtime path stays uniform.
    """
    return _tool_error(
        ErrorKind.CANCELLED,
        TOOL_CANCELLED_CODE,
        retryable=False,
        detail=f"{name!r} was cancelled",
        context={"tool": name},
    )


def tool_failed(name: str, *, detail: str, cause: AppError | None = None) -> AppError:
    """A tool raised an unexpected failure during execution (doc 20 §15)."""
    return _tool_error(
        ErrorKind.INTERNAL,
        TOOL_FAILED_CODE,
        retryable=False,
        detail=f"{name!r} failed: {detail}",
        cause=cause,
        context={"tool": name},
    )


def duplicate_tool(name: str) -> AppError:
    """A tool is already registered under ``name`` (doc 20 §11)."""
    return _tool_error(
        ErrorKind.CONFLICT,
        TOOL_DUPLICATE_CODE,
        retryable=False,
        detail=f"a tool is already registered as {name!r}",
        context={"tool": name},
    )


def _tool_error(
    kind: ErrorKind,
    code: str,
    *,
    retryable: bool,
    detail: str,
    cause: AppError | None = None,
    context: Mapping[str, Any] | None = None,
) -> AppError:
    return AppError(
        kind=kind,
        code=code,
        message_key=f"hata.{code}",
        retryable=retryable,
        detail=detail,
        cause=cause,
        context=context,
    )
