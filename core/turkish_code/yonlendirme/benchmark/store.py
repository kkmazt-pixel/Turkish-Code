"""Cached benchmark results (doc 50 §7/§9).

Profiles are disposable and rebuildable (re-probe) — losing this cache costs
a re-measurement, never user data. Process-lifetime only until Storage
(doc 29) exists; interface-stable per PR-8.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from turkish_code.yonlendirme.benchmark.profile import PerformanceProfile


@runtime_checkable
class BenchmarkStore(Protocol):
    """Stores the latest :class:`PerformanceProfile` per ``(provider, model)``."""

    def get(self, provider_id: str, model_id: str) -> PerformanceProfile | None:
        """Return the cached profile, or ``None`` if never probed."""
        ...

    def put(self, provider_id: str, model_id: str, profile: PerformanceProfile) -> None:
        """Store (overwrite) the profile for ``(provider_id, model_id)``."""
        ...


class InMemoryBenchmarkStore:
    """Process-lifetime :class:`BenchmarkStore` (doc 50 §7)."""

    def __init__(self) -> None:
        self._profiles: dict[tuple[str, str], PerformanceProfile] = {}

    def get(self, provider_id: str, model_id: str) -> PerformanceProfile | None:
        return self._profiles.get((provider_id, model_id))

    def put(self, provider_id: str, model_id: str, profile: PerformanceProfile) -> None:
        self._profiles[(provider_id, model_id)] = profile
