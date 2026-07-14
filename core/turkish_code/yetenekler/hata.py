"""Skill-runtime failures as typed :class:`AppError` values (doc 19 §7, doc 38).

The Skill Runtime never lets a raw exception escape: a duplicate id is a
``CONFLICT``, an unknown skill is ``NOT_FOUND``, and — as later increments add
them — dispatch failures map to ``TIMEOUT``/``CANCELLED``/``INTERNAL`` (doc 38
§4/§7). Codes are stable machine strings; renaming one is a migration.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from turkish_code.hata import AppError, ErrorKind

SKILL_NOT_FOUND_CODE = "skill.not_found"
SKILL_DUPLICATE_CODE = "skill.duplicate"
SKILL_TOOL_OUT_OF_SCOPE_CODE = "skill.tool_out_of_scope"
SKILL_TIMEOUT_CODE = "skill.timeout"
SKILL_CANCELLED_CODE = "skill.cancelled"
SKILL_FAILED_CODE = "skill.failed"


def skill_timeout(skill_id: str, timeout_ms: int) -> AppError:
    """Invocation exceeded the skill's deadline (doc 19 §14)."""
    return skill_error(
        ErrorKind.TIMEOUT,
        SKILL_TIMEOUT_CODE,
        detail=f"{skill_id!r} exceeded {timeout_ms}ms",
        retryable=True,
        context={"skill": skill_id, "timeoutMs": timeout_ms},
    )


def skill_cancelled(skill_id: str) -> AppError:
    """The invocation was cooperatively cancelled (doc 10 §10, doc 19 §14)."""
    return skill_error(
        ErrorKind.CANCELLED,
        SKILL_CANCELLED_CODE,
        detail=f"{skill_id!r} was cancelled",
        context={"skill": skill_id},
    )


def skill_failed(
    skill_id: str, *, detail: str, cause: AppError | None = None
) -> AppError:
    """A skill raised an unexpected failure during execution (doc 19 §14)."""
    return skill_error(
        ErrorKind.INTERNAL,
        SKILL_FAILED_CODE,
        detail=f"{skill_id!r} failed: {detail}",
        cause=cause,
        context={"skill": skill_id},
    )


def tool_out_of_scope(tool_name: str) -> AppError:
    """The skill referenced a tool outside its ``allowed_tools`` (doc 19 §4/§15)."""
    return skill_error(
        ErrorKind.PERMISSION,
        SKILL_TOOL_OUT_OF_SCOPE_CODE,
        detail=f"skill not allowed tool {tool_name!r}",
        context={"tool": tool_name},
    )


def skill_not_found(skill_id: str) -> AppError:
    """No skill is registered under ``skill_id`` (doc 19 §7)."""
    return skill_error(
        ErrorKind.NOT_FOUND,
        SKILL_NOT_FOUND_CODE,
        detail=f"no skill registered as {skill_id!r}",
        context={"skill": skill_id},
    )


def duplicate_skill(skill_id: str) -> AppError:
    """A skill is already registered under ``skill_id`` (doc 19 §7)."""
    return skill_error(
        ErrorKind.CONFLICT,
        SKILL_DUPLICATE_CODE,
        detail=f"a skill is already registered as {skill_id!r}",
        context={"skill": skill_id},
    )


def skill_error(
    kind: ErrorKind,
    code: str,
    *,
    detail: str,
    retryable: bool = False,
    cause: AppError | None = None,
    context: Mapping[str, Any] | None = None,
) -> AppError:
    """Build a typed skill :class:`AppError` (shared by the runtime modules)."""
    return AppError(
        kind=kind,
        code=code,
        message_key=f"hata.{code}",
        retryable=retryable,
        detail=detail,
        cause=cause,
        context=context,
    )
