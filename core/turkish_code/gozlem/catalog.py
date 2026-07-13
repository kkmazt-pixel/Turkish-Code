"""The metric catalog (doc 51 §4) — named, typed measurements.

No ad-hoc, unnamed metrics (doc 51 §12): every metric emitted anywhere in the
provider/routing layer must be one of these names. Bucket boundaries and
retention are left `OPEN` per doc 51's own note; this fixes the *catalog*.
"""

from __future__ import annotations

from enum import StrEnum


class MetricKind(StrEnum):
    """How a metric accumulates (doc 51 §4)."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class MetricName(StrEnum):
    """The canonical baseline catalog (doc 51 §4); extend additively (PR-18)."""

    ROUTE_REQUESTS = "route.requests"
    ROUTE_SELECTED_MODEL = "route.selected_model"
    ROUTE_DECISION_LATENCY = "route.decision_latency"
    ROUTE_DEGRADED = "route.degraded"
    ROUTE_UNROUTABLE = "route.unroutable"

    PROVIDER_CALLS = "provider.calls"
    PROVIDER_LATENCY = "provider.latency"
    PROVIDER_HEALTH = "provider.health"
    PROVIDER_RELIABILITY = "provider.reliability"

    FAILOVER_EVENTS = "failover.events"
    RETRY_ATTEMPTS = "retry.attempts"
    COOLDOWN_ENTERED = "cooldown.entered"
    OFFLINE_FALLBACK_USED = "offline_fallback.used"

    QUOTA_HEADROOM = "quota.headroom"
    QUOTA_EXHAUSTED = "quota.exhausted"
    COST_ESTIMATED = "cost.estimated"

    MODEL_CACHE_HITS = "model_cache.hits"
    MODEL_CACHE_MISSES = "model_cache.misses"
    MODEL_CACHE_REFRESHES = "model_cache.refreshes"


_KIND_OF: dict[MetricName, MetricKind] = {
    MetricName.ROUTE_REQUESTS: MetricKind.COUNTER,
    MetricName.ROUTE_SELECTED_MODEL: MetricKind.COUNTER,
    MetricName.ROUTE_DECISION_LATENCY: MetricKind.HISTOGRAM,
    MetricName.ROUTE_DEGRADED: MetricKind.COUNTER,
    MetricName.ROUTE_UNROUTABLE: MetricKind.COUNTER,
    MetricName.PROVIDER_CALLS: MetricKind.COUNTER,
    MetricName.PROVIDER_LATENCY: MetricKind.HISTOGRAM,
    MetricName.PROVIDER_HEALTH: MetricKind.GAUGE,
    MetricName.PROVIDER_RELIABILITY: MetricKind.GAUGE,
    MetricName.FAILOVER_EVENTS: MetricKind.COUNTER,
    MetricName.RETRY_ATTEMPTS: MetricKind.COUNTER,
    MetricName.COOLDOWN_ENTERED: MetricKind.COUNTER,
    MetricName.OFFLINE_FALLBACK_USED: MetricKind.COUNTER,
    MetricName.QUOTA_HEADROOM: MetricKind.GAUGE,
    MetricName.QUOTA_EXHAUSTED: MetricKind.COUNTER,
    MetricName.COST_ESTIMATED: MetricKind.COUNTER,
    MetricName.MODEL_CACHE_HITS: MetricKind.COUNTER,
    MetricName.MODEL_CACHE_MISSES: MetricKind.COUNTER,
    MetricName.MODEL_CACHE_REFRESHES: MetricKind.COUNTER,
}


def kind_of(name: MetricName) -> MetricKind:
    """The accumulation kind (counter/gauge/histogram) for ``name`` (doc 51 §4)."""
    return _KIND_OF[name]
