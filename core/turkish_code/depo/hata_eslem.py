"""SQLite driver errors → typed :class:`AppError` (doc 29 §14, doc 38).

The storage boundary never lets a raw ``sqlite3`` exception escape (doc 38 §7):
a locked DB or disk-full is a retryable ``RESOURCE`` error, a malformed file is
``CORRUPTION`` (rebuild-from-source territory, doc 29 §15), a constraint breach
is ``CONFLICT``, and anything else is a non-retryable ``INTERNAL`` error.
"""

from __future__ import annotations

import sqlite3

from turkish_code.hata import AppError, ErrorKind

STORAGE_LOCKED_CODE = "storage.locked"
STORAGE_IO_CODE = "storage.io_error"
STORAGE_CORRUPT_CODE = "storage.corrupt"
STORAGE_CONFLICT_CODE = "storage.constraint"
STORAGE_INTERNAL_CODE = "storage.internal"

_LOCK_MARKERS = ("database is locked", "database is busy")
_IO_MARKERS = ("disk i/o error", "disk full", "database or disk is full")
_CORRUPT_MARKERS = ("malformed", "not a database", "file is encrypted")


def map_sqlite_error(exc: sqlite3.Error) -> AppError:
    """Translate a ``sqlite3`` exception into a typed :class:`AppError`."""
    if isinstance(exc, sqlite3.IntegrityError):
        return _err(ErrorKind.CONFLICT, STORAGE_CONFLICT_CODE, exc, retryable=False)

    message = str(exc).lower()
    if any(marker in message for marker in _LOCK_MARKERS):
        return _err(ErrorKind.RESOURCE, STORAGE_LOCKED_CODE, exc, retryable=True)
    if any(marker in message for marker in _IO_MARKERS):
        return _err(ErrorKind.RESOURCE, STORAGE_IO_CODE, exc, retryable=False)
    if any(marker in message for marker in _CORRUPT_MARKERS):
        return _err(ErrorKind.CORRUPTION, STORAGE_CORRUPT_CODE, exc, retryable=False)

    return _err(ErrorKind.INTERNAL, STORAGE_INTERNAL_CODE, exc, retryable=False)


def _err(
    kind: ErrorKind, code: str, exc: sqlite3.Error, *, retryable: bool
) -> AppError:
    return AppError(
        kind=kind,
        code=code,
        message_key=f"hata.{code}",
        retryable=retryable,
        detail=f"{type(exc).__name__}: {exc}",
    )
