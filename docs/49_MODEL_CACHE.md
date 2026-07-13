# 49 — Model Cache (Model Önbelleği)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `saglayicilar/cache/`
> **New** ([52_ADR_LOG](./52_ADR_LOG.md) ADR-0013). Recovered: `PROJECT_ANALYSIS.md` L83/L96 (24-hour model cache).
> **Related:** [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) · [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) · [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md)

---

## 1. Purpose

Defines the **model cache** — a local cache of each provider's available models (and their metadata/capabilities) so the system doesn't re-enumerate providers on every run. The recovered decision is a **24-hour cache** ([52](./52_ADR_LOG.md) ADR-0013). It makes startup and routing fast while keeping the model registry reasonably fresh.

## 2. Scope

What is cached, the 24h TTL + refresh policy, invalidation, staleness handling, and the boundary to the registry/router. Out of scope: routing ([45](./45_ROUTING_ORCHESTRATION.md)), provider execution ([21](./21_PROVIDER_SYSTEM.md)), quota ([48](./48_QUOTA_TIER_MANAGEMENT.md)).

## 3. Goals

1. Avoid re-enumerating provider models every run (fast startup/routing).
2. Keep the registry **fresh enough** (24h default) without hammering provider list endpoints.
3. **Refresh gracefully** (background/on-demand) without blocking routing.
4. Survive offline: serve the last-good cache when providers are unreachable ([32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md)).

### Non-Goals
- Not a response cache (this caches the *model catalog*, not completions). Not quota state ([48](./48_QUOTA_TIER_MANAGEMENT.md)).

## 4. What Is Cached

- Per provider: the list of `ModelInfo` from `listModels()` ([21](./21_PROVIDER_SYSTEM.md) §5) — model ids, roles, capabilities ([46](./46_CAPABILITY_TAXONOMY.md)), context windows, pricing/tier hints ([22](./22_PROVIDER_INTEGRATIONS.md)).
- OpenRouter's aggregated model list (expanded) is cached like any provider's.
- Cache entries carry a **fetchedAt** timestamp and provider id.

## 5. TTL & Refresh Policy (ADR-0013)

```
default TTL = 24h
on registry request:
  entry fresh (age < TTL)      → serve cached
  entry stale (age ≥ TTL)      → serve cached immediately + trigger BACKGROUND refresh
  entry missing                → fetch (blocking, bounded timeout) or serve empty + async fetch
manual "refresh models" (UI)   → force refresh now
provider newly configured      → fetch on demand
```

- **Serve-stale-while-revalidate**: never block routing on a refresh; use the last-good list and update in the background (availability > absolute freshness).
- Refresh failures keep the last-good cache and log a metric ([51](./51_METRICS.md)); no hard failure.

> **OPEN (design):** exact **refresh triggers, backoff on failed refresh, and per-provider TTL overrides** are a recovered gap (`PROJECT_ANALYSIS.md` L83). The 24h default + serve-stale shape is fixed; specifics finalized in implementation.

## 6. Invalidation & Staleness

- Manual refresh (UI, [06](./06_COMPONENT_LIBRARY.md)); on provider (re)configuration; on repeated "model not found" errors during routing (a signal the cache is stale → force refresh).
- Stale-but-served entries are marked so the UI can show "model list last updated X ago."

## 7. Directory / Config / Dependencies

```
saglayicilar/cache/
  model_cache.py   # store + TTL + serve-stale-while-revalidate
  refresh.py       # background/on-demand refresh
```
Storage: a light local store (JSON/SQLite; [29](./29_STORAGE.md) options — deliberately light, ADR-0010), **no secrets**. TTL/override config ([33_CONFIGURATION](./33_CONFIGURATION.md)). Feeds [21](./21_PROVIDER_SYSTEM.md) registry / [45](./45_ROUTING_ORCHESTRATION.md).

## 8. Edge Cases

- **Offline at startup:** serve last-good cache so routing to Ollama (and any reachable provider) still works ([32](./32_OFFLINE_FIRST.md)).
- **Provider added a new model:** appears after next refresh (≤24h) or manual refresh.
- **Provider removed a model** the router picked: routing "model not found" → force refresh + re-candidate ([45](./45_ROUTING_ORCHESTRATION.md)).
- **Corrupt cache file:** discard + re-fetch (or serve empty + async fetch); never crash.
- **First run, no cache, offline:** only Ollama/local models available; cloud models appear once online + fetched.

## 9. Failure Recovery / Security / Performance

- Cache is disposable/rebuildable (re-fetch from providers) — no user-data risk. No secrets cached ([34](./34_API_KEYS.md)/[30](./30_SECURITY.md)). Serving cached lists is O(1); refresh is background ([31](./31_PERFORMANCE.md)).

## 10. Testing Strategy

- 24h TTL honored; stale entry served + background refresh triggered; manual refresh forces fetch; offline serves last-good; "model not found" forces refresh; corrupt cache recovers. See [35_TESTING](./35_TESTING.md).

## 11. Future Extensions

- Per-provider adaptive TTL; ETag/conditional fetches; diff notifications ("new model available").

## 12. Anti-Patterns

- Blocking routing on a synchronous refresh (must serve-stale).
- Re-enumerating providers every run (defeats the cache).
- Caching secrets.
- Hard-failing on a corrupt/missing cache.

## 13. Things That Must Never Happen

1. Routing blocks on a model-list refresh.
2. Provider models are re-enumerated on every run.
3. Secrets are written into the model cache.
4. A corrupt cache crashes startup instead of re-fetching.

## 14. Relationship With Other Subsystems

Backs the registry in [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md); consumed by [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md); sourced from [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md); refresh surfaced in [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md); offline behavior [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md); rationale [52_ADR_LOG](./52_ADR_LOG.md).

## 15. Migration Considerations

- The 24h TTL + serve-stale model is stable; refresh specifics are `OPEN` until implementation. Cache format is versioned; a format change just triggers a re-fetch (no data loss).
