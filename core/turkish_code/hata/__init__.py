"""Typed error subsystem for the Çekirdek (doc 38).

Public surface: the :class:`AppError` value and the :class:`ErrorKind`
taxonomy. Every failure in the core is expressed as an ``AppError`` (PR-10);
nothing else in the package should define its own ad-hoc exception hierarchy.
"""

from turkish_code.hata.app_error import AppError
from turkish_code.hata.kinds import ErrorKind

__all__ = ["AppError", "ErrorKind"]
