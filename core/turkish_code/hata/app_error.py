"""The typed error value used throughout the Çekirdek (doc 38 §5).

``AppError`` makes failures *values* — categorized, retryable-or-not, with a
localizable message and remedy — rather than silent exceptions (PR-10). It is
raised and allowed to bubble as a typed value (doc 38 §7); at the Core Channel
boundary ``kanal/`` turns it into a JSON-RPC ``error`` object whose
``error.data`` is produced by :meth:`AppError.to_error_data` (doc 10 §14).

Design notes:
- It subclasses ``Exception`` so it can be ``raise``d and propagated, yet its
  fields are treated as read-only — an error is an immutable value once built.
- ``detail`` and ``context`` are for logs only (doc 39) and are **never** part
  of the user-facing surface payload; the ``cause`` chain is preserved for logs
  but flattened to a single message at the surface (doc 38 §6). Accordingly,
  :meth:`to_error_data` deliberately omits ``detail`` and ``cause``.
- Redaction of secrets from ``context`` is a separate cross-cutting pass
  (doc 34 / doc 30) applied before logging; this type stores what it is given.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from turkish_code.hata.kinds import ErrorKind

# The subset of fields that is safe to surface to the caller/UI (doc 38 §6).
# `detail` and `cause` are intentionally excluded (log-only / flattened).
_SurfaceData = dict[str, Any]


class AppError(Exception):
    """A structured, typed failure (doc 38 §5).

    Args:
        kind: The taxonomy category (doc 38 §4).
        code: Stable machine code, e.g. ``"tool.args.invalid"``. Used by the
            agent and analytics; renaming it is a migration (doc 38 §23).
        message_key: i18n key resolving to the Turkish user message (doc 04
            §12); errors are never raw English strings (PR-12).
        retryable: Whether the caller/agent may sensibly retry (doc 38 §7).
        detail: Developer detail for logs only — never shown raw to the user.
        remedy_key: i18n key resolving to a "what to do" hint, e.g.
            ``"caba.hizli_dene"``.
        cause: The underlying :class:`AppError`, preserved for log chaining.
        context: Redacted structured context for logs (no secrets, doc 34).

    The constructor is keyword-only to keep call sites self-documenting at the
    point of failure (doc 38 §7) and to make adding fields non-breaking.
    """

    __slots__ = (
        "kind",
        "code",
        "message_key",
        "retryable",
        "detail",
        "remedy_key",
        "cause",
        "context",
    )

    def __init__(
        self,
        *,
        kind: ErrorKind,
        code: str,
        message_key: str,
        retryable: bool,
        detail: str | None = None,
        remedy_key: str | None = None,
        cause: AppError | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        if not code:
            raise ValueError("AppError.code must be a non-empty stable code")
        if not message_key:
            raise ValueError("AppError.message_key must be a non-empty i18n key")

        # `code` is the human-readable summary carried by the base Exception;
        # it is a stable machine code and never contains secrets or user text.
        super().__init__(code)

        self.kind = kind
        self.code = code
        self.message_key = message_key
        self.retryable = retryable
        self.detail = detail
        self.remedy_key = remedy_key
        self.cause = cause
        # Freeze context into a read-only, defensively-copied snapshot so the
        # error stays an immutable value even if the caller mutates its dict.
        self.context: Mapping[str, Any] | None = (
            MappingProxyType(dict(context)) if context is not None else None
        )

    def to_error_data(self) -> _SurfaceData:
        """Build the ``error.data`` surface payload (doc 38 §6, doc 10 §14).

        Contains only what the caller/agent/UI may act on: ``kind``, ``code``,
        ``retryable``, and the optional ``messageKey``/``remedy``/``context``.
        ``detail`` and the ``cause`` chain are intentionally excluded — they are
        log-only and are flattened to a single user message at the surface.
        Keys use the wire spelling (``messageKey``/``remedy``) from doc 38 §19.
        """
        data: _SurfaceData = {
            "kind": self.kind.value,
            "code": self.code,
            "messageKey": self.message_key,
            "retryable": self.retryable,
        }
        if self.remedy_key is not None:
            data["remedy"] = self.remedy_key
        if self.context is not None:
            data["context"] = dict(self.context)
        return data

    def causes(self) -> list[AppError]:
        """Return this error's cause chain, nearest cause first (doc 38 §6).

        Used by logging (doc 39) to record the full chain; the user surface
        only ever shows the top-level error.
        """
        chain: list[AppError] = []
        current = self.cause
        while current is not None:
            chain.append(current)
            current = current.cause
        return chain

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"AppError(kind={self.kind.value!r}, code={self.code!r}, "
            f"retryable={self.retryable!r})"
        )
