"""Redaction filter for log records (doc 39 §8 — non-negotiable).

Two layers of defense (doc 34 / doc 30 §7):

1. **Field-name masking** — a value whose field name hints at a secret is
   dropped entirely.
2. **Value-pattern scrubbing** — secret-shaped substrings (API keys, bearer
   tokens) are masked wherever they appear: in a field value *or* inside free
   text such as a log ``msg`` or an error ``detail``.

Secrets should never reach a log call site in the first place (doc 34); this is
the safety net. The pattern set is intentionally conservative and is expected to
grow as new secret shapes appear (doc 39 §23).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Protocol

# Field-name substrings that indicate secret material (doc 34 / doc 30 §7).
# Intentionally specific to avoid masking innocent names (e.g. bare "key").
_SENSITIVE_HINTS: tuple[str, ...] = (
    "secret",
    "token",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "authorization",
    "credential",
)

# Secret-shaped value patterns (doc 39 §8/§23). Covers the shapes used by the
# project's providers (sk-… for OpenAI-compatible incl. Groq/OpenRouter, AIza…
# for Gemini) plus common bearer/PAT shapes. Extend as new shapes appear.
_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{12,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{8,}"),
    re.compile(r"gh[posru]_[A-Za-z0-9]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{6,}"),
)
_MASK = "***"


class Redactor(Protocol):
    """Removes secret material from log fields and free text (doc 39 §8)."""

    def redact(self, fields: Mapping[str, Any]) -> dict[str, Any]:
        """Return a copy of ``fields`` with sensitive entries masked."""
        ...

    def redact_text(self, text: str) -> str:
        """Return ``text`` with any secret-shaped substrings masked."""
        ...


class FieldNameRedactor:
    """Default redactor: field-name masking plus value-pattern scrubbing (doc 39 §8)."""

    def redact(self, fields: Mapping[str, Any]) -> dict[str, Any]:
        """Mask sensitively-named values; scrub secret patterns from string values."""
        result: dict[str, Any] = {}
        for key, value in fields.items():
            if self._is_sensitive(key):
                result[key] = _MASK
            elif isinstance(value, str):
                result[key] = self.redact_text(value)
            else:
                result[key] = value
        return result

    def redact_text(self, text: str) -> str:
        """Replace every secret-shaped substring in ``text`` with the mask."""
        scrubbed = text
        for pattern in _SECRET_VALUE_PATTERNS:
            scrubbed = pattern.sub(_MASK, scrubbed)
        return scrubbed

    @staticmethod
    def _is_sensitive(name: str) -> bool:
        lowered = name.lower()
        return any(hint in lowered for hint in _SENSITIVE_HINTS)
