"""Error taxonomy for turkish.code (doc 38 §4).

`ErrorKind` is the shared, versioned category enum every `AppError` carries.
Its string values are the **stable wire values** placed in the JSON-RPC
``error.data.kind`` field (doc 10 §14) and mirrored by the Kabuk error types
and ``packages/ipc-schema`` (doc 38 §6). Adding a kind is additive (PR-18);
renaming a value is a breaking migration and must not be done casually.
"""

from __future__ import annotations

from enum import StrEnum


class ErrorKind(StrEnum):
    """Category of a failure, shared across all three tiers (doc 38 §4).

    A ``StrEnum`` so the member serializes to its wire value directly
    (e.g. ``json.dumps`` yields ``"Timeout"``), keeping the taxonomy identical
    on the Python, Rust, and TypeScript sides of the contract.
    """

    VALIDATION = "Validation"
    """Bad input: malformed tool args, invalid request (doc 20)."""

    PERMISSION = "Permission"
    """A capability was denied by the permission engine (doc 24)."""

    NOT_FOUND = "NotFound"
    """A referenced file, entity, or model does not exist."""

    CONFLICT = "Conflict"
    """Edit conflict or version skew (doc 27 / doc 10)."""

    PROVIDER = "Provider"
    """Model/provider failure, e.g. context-window exceeded (doc 21)."""

    EGRESS = "Egress"
    """Offline, no consent, or network egress blocked (doc 30 / doc 32)."""

    RESOURCE = "Resource"
    """Disk full, OOM, or GPU OOM (doc 29 / doc 31)."""

    BUDGET = "Budget"
    """Effort budget exhausted (doc 17)."""

    TIMEOUT = "Timeout"
    """A deadline was exceeded (doc 10)."""

    CANCELLED = "Cancelled"
    """The user cancelled the operation; not an error state (doc 10)."""

    CORRUPTION = "Corruption"
    """A rebuildable derived index/store is corrupt (doc 13 / doc 29)."""

    INTERNAL = "Internal"
    """An unexpected bug; report, do not retry."""

    SECURITY = "Security"
    """Integrity/signature/sandbox violation; fail closed (doc 30)."""
