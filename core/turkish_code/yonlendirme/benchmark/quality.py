"""Light quality signal (doc 50 §4).

Not a rigorous eval harness (doc 50 §3 non-goal) — a curated heuristic seed
derived from a model's already-declared capabilities, explicitly marked
low-confidence until a richer evaluation exists (doc 50 §11).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from turkish_code.yonlendirme.capability.taxonomy import CapabilitySet

Confidence = Literal["low", "medium", "high"]

_REASONING_MAX = 3  # ReasoningDepth.EXPERT
_CODE_APTITUDE_MAX = 3  # CodeAptitude.EXPERT
_MULTILINGUAL_MAX = 2  # MultilingualTr.STRONG


@dataclass(frozen=True, slots=True)
class QualitySignal:
    """A quality estimate in ``[0, 1]`` with its evidence confidence (doc 50 §4)."""

    score: float
    confidence: Confidence


def seed_quality(capabilities: CapabilitySet) -> QualitySignal:
    """Derive a low-confidence quality seed from declared capabilities (doc 50 §4).

    Averages the normalized ``reasoning``, ``code_aptitude``, and
    ``multilingual_tr`` ordinals (each already 0-indexed with a known max).
    This is a curated heuristic, not a measured eval — always ``"low"``
    confidence until a real quality probe/eval exists (doc 50 §11).
    """
    reasoning_fraction = capabilities.reasoning / _REASONING_MAX
    code_fraction = capabilities.code_aptitude / _CODE_APTITUDE_MAX
    turkish_fraction = capabilities.multilingual_tr / _MULTILINGUAL_MAX
    score = (reasoning_fraction + code_fraction + turkish_fraction) / 3
    return QualitySignal(score=score, confidence="low")
