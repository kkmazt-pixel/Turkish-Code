# 51 — Metrics & Observability (Metrikler)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `gozlem/` (+ [39_LOGGING](./39_LOGGING.md))
> **New** ([52_ADR_LOG](./52_ADR_LOG.md) ADR-0003/0006). Recovered gap: `PROJECT_ANALYSIS.md` L90 (metrics definitions), L77 (logging/observability).
> **Related:** [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) · [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md) · [39_LOGGING](./39_LOGGING.md) · [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md)

---

## 1. Purpose

Defines the **metrics catalog** — the named, structured measurements of the provider/routing layer's *live behavior* (not probing — that's [50](./50_BENCHMARK_SPEEDTEST.md)). Metrics make the system **observable**: which models/providers are used, how routing decides, failover/quota/health over time. They power the provider-status UI ([06](./06_COMPONENT_LIBRARY.md)), scoring's reliability factor ([47](./47_SCORING_ALGORITHMS.md)), and diagnostics — all **local** ([39_LOGGING](./39_LOGGING.md), no auto-egress).

## 2. Scope

The metric definitions (names, types, dimensions), collection points, storage, and consumers. Out of scope: benchmark probing ([50](./50_BENCHMARK_SPEEDTEST.md)), generic app logging semantics ([39](./39_LOGGING.md)), scoring math ([47](./47_SCORING_ALGORITHMS.md)).

## 3. Goals

1. A **defined catalog** (no ad-hoc, unnamed metrics) — legible to humans + UI (PR-11).
2. Cover **routing, providers, quota, failover, latency, cost** so behavior is explainable.
3. Feed **reliability** back into scoring ([47](./47_SCORING_ALGORITHMS.md)) and status into the UI ([06](./06_COMPONENT_LIBRARY.md)).
4. Stay **local & secret-free** ([39](./39_LOGGING.md)/[30](./30_SECURITY.md)); no telemetry egress by default.

### Non-Goals
- Not remote telemetry (none by default). Not benchmarking ([50](./50_BENCHMARK_SPEEDTEST.md)).

## 4. Metric Catalog

Grouped; each has a name, type (counter/gauge/histogram), and dimensions (provider, model, mode, role).

**Routing:**
- `route.requests` (counter; dims: mode, role) — routing requests.
- `route.selected_model` (counter; dims: model, provider) — chosen model distribution.
- `route.decision_latency` (histogram) — time to decide.
- `route.degraded` (counter) — degraded (nearest-capability) selections.
- `route.unroutable` (counter) — no viable model (should be ~0).

**Providers / health:**
- `provider.calls` (counter; dims: provider, model, outcome=success|error|timeout).
- `provider.latency` (histogram; dims: provider, model) — ttft/total.
- `provider.health` (gauge; dims: provider) — up/degraded/cooling/down.
- `provider.reliability` (gauge; dims: provider) — rolling success rate → scoring ([47](./47_SCORING_ALGORITHMS.md)).

**Failover / resilience:**
- `failover.events` (counter; dims: from_provider→to_provider, reason).
- `retry.attempts` (counter; dims: provider, reason).
- `cooldown.entered` (counter; dims: provider, reason).
- `offline_fallback.used` (counter) — Ollama fallback engaged ([32](./32_OFFLINE_FIRST.md)).

**Quota / cost:**
- `quota.headroom` (gauge; dims: provider, tier) — remaining quota.
- `quota.exhausted` (counter; dims: provider) — exhaustion events.
- `cost.estimated` (counter; dims: provider, model) — estimated spend (from pricing [22](./22_PROVIDER_INTEGRATIONS.md)).

**Cache:**
- `model_cache.hits` / `.misses` / `.refreshes` (counters) ([49](./49_MODEL_CACHE.md)).

> **OPEN (design):** exact **bucket boundaries, retention, and any additional metrics** are a recovered gap (`PROJECT_ANALYSIS.md` L90). The catalog above is the canonical baseline; extend additively.

## 5. Collection & Storage

- Metrics are emitted at the routing/provider/quota/cache code points and aggregated in-process; persisted lightly (in-memory + optional local rollups, [29](./29_STORAGE.md) options). Correlated with runs via `runId`/`traceId` ([10](./10_IPC.md)/[26](./26_TIMELINE.md)).
- **Local only**; exposed to the UI ([06](./06_COMPONENT_LIBRARY.md)) and logs ([39](./39_LOGGING.md)); **no egress** without explicit consent ([30](./30_SECURITY.md), ADR-0010 keeps this light but privacy on metrics still holds — metrics can reveal usage).

## 6. Consumers

- **UI:** provider status / health / cost dashboards ([06](./06_COMPONENT_LIBRARY.md) provider status, speed test [50](./50_BENCHMARK_SPEEDTEST.md)).
- **Scoring:** `provider.reliability` feeds `providerScore` ([47](./47_SCORING_ALGORITHMS.md) §5).
- **Diagnostics:** logs ([39](./39_LOGGING.md)); routing decisions link to metrics.

## 7. Directory / Config / Dependencies

```
gozlem/
  catalog.py     # metric names/types/dims (this doc)
  collect.py     # emission at routing/provider/quota/cache points
  rollup.py      # aggregation + light local storage
```
Retention/rollup config ([33_CONFIGURATION](./33_CONFIGURATION.md)). Emitted by [45](./45_ROUTING_ORCHESTRATION.md)/[21](./21_PROVIDER_SYSTEM.md)/[48](./48_QUOTA_TIER_MANAGEMENT.md)/[49](./49_MODEL_CACHE.md); consumed by [06](./06_COMPONENT_LIBRARY.md)/[47](./47_SCORING_ALGORITHMS.md)/[39](./39_LOGGING.md).

## 8. Edge Cases

- **High-cardinality dims** (many models): cap/aggregate to avoid unbounded growth (PR-14).
- **Metric emission failure:** best-effort; never blocks a real call ([39](./39_LOGGING.md) philosophy).
- **Restart:** in-memory metrics reset; persisted rollups (if enabled) survive.
- **Secret in a dimension:** forbidden — dims are provider/model/mode/role only, never keys ([34](./34_API_KEYS.md)).

## 9. Failure Recovery / Security / Performance

- Metrics are non-critical; failures degrade silently (for metrics only). **No secrets** in metric names/dims/values ([30](./30_SECURITY.md)/[34](./34_API_KEYS.md)); **no egress** by default. Emission is O(1), off the hot path ([31](./31_PERFORMANCE.md)).

## 10. Testing Strategy

- Each metric emitted at its code point with correct dims; reliability feeds scoring; no secrets in dims; high-cardinality capped; emission failure non-blocking. See [35_TESTING](./35_TESTING.md).

## 11. Future Extensions

- Opt-in, consented, anonymized aggregate export ([30](./30_SECURITY.md)); Prometheus/OpenTelemetry local exporter; historical trend charts; cost-over-time budgeting ([48](./48_QUOTA_TIER_MANAGEMENT.md)).

## 12. Anti-Patterns

- Ad-hoc unnamed metrics (must be in the catalog).
- Secrets/PII in dimensions.
- Unbounded cardinality.
- Auto-egressing metrics as telemetry.
- Metric emission blocking real calls.

## 13. Things That Must Never Happen

1. A secret appears in a metric name/dimension/value.
2. Metrics auto-egress without consent.
3. Metric cardinality grows unbounded.
4. Metric emission blocks or fails a user operation.

## 14. Relationship With Other Subsystems

Observes [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md)/[21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md)/[48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md)/[49_MODEL_CACHE](./49_MODEL_CACHE.md); feeds [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md) + UI [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md); sinks to [39_LOGGING](./39_LOGGING.md); distinct from probing [50_BENCHMARK_SPEEDTEST](./50_BENCHMARK_SPEEDTEST.md); constrained by [30_SECURITY](./30_SECURITY.md); rationale [52_ADR_LOG](./52_ADR_LOG.md).

## 15. Migration Considerations

- The catalog is versioned; adding metrics is additive (PR-18). Buckets/retention are `OPEN` until implementation. Any future export is a consented, major feature ([30](./30_SECURITY.md)).
