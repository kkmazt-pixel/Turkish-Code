"""Context assembly (doc 13 §9) — Bağlam Kurulumu, the step that builds what
the model actually sees. Interface + the assembled-context value only; the
dedupe/order/budget-pack/cite logic is a future increment.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from turkish_code.getirim.getirici import RetrievedCandidate
from turkish_code.getirim.parca import Chunk


@dataclass(frozen=True, slots=True)
class AssembledContext:
    """The final, budget-fit, cited context handed to Muhakeme (doc 13 §9)."""

    chunks: Sequence[Chunk]
    total_tokens: int


@runtime_checkable
class ContextAssembler(Protocol):
    """Dedupes, orders, budget-packs, and cites candidates (doc 13 §9)."""

    def assemble(
        self, candidates: Sequence[RetrievedCandidate], *, token_budget: int
    ) -> AssembledContext:
        """Build the final context from ``candidates`` within ``token_budget``."""
        ...
