"""Quota & tier management (doc 48) — tracks provider usage against tier
limits, exposes headroom/cooldown signals to the scorer/router, and enforces
quality-under-exhaustion (ADR-0006): quota draining degrades to the best
*available* model, never a poor default.
"""

from turkish_code.yonlendirme.quota.headroom import CooldownState, ProviderQuotaState
from turkish_code.yonlendirme.quota.store import InMemoryQuotaStore, QuotaStore
from turkish_code.yonlendirme.quota.tracker import QuotaTracker

__all__ = [
    "QuotaStore",
    "InMemoryQuotaStore",
    "ProviderQuotaState",
    "CooldownState",
    "QuotaTracker",
]
