# 50 — Benchmark & Speed Test (Kıyaslama ve Hız Testi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `yonlendirme/benchmark/` + Arayüz speed-test UI
> **New** ([52_ADR_LOG](./52_ADR_LOG.md) ADR-0005/0006). Recovered: `PROJECT_ANALYSIS.md` L52 (speed test), L85 (benchmark methodology), L45 (performance profiles).
> **Related:** [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md) · [46_CAPABILITY_TAXONOMY](./46_CAPABILITY_TAXONOMY.md) · [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) · [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md)

---

## 1. Purpose

Defines how turkish.code **measures models/providers** to produce the **latency and quality evidence** that scoring ([47](./47_SCORING_ALGORITHMS.md)) and the capability taxonomy ([46](./46_CAPABILITY_TAXONOMY.md)) rely on — and the user-facing **speed test** (`PROJECT_ANALYSIS.md` L52) plus **performance profiles** (L45). Without measurement, "best model" and "fastest provider" are guesses; this subsystem grounds them in data.

## 2. Scope

The benchmark methodology (latency, throughput, quality signals), the user-facing speed test, performance profiles, how results feed scoring/capabilities, and result storage. Out of scope: the scoring math ([47](./47_SCORING_ALGORITHMS.md)), routing ([45](./45_ROUTING_ORCHESTRATION.md)), metrics/observability of live traffic ([51](./51_METRICS.md) — that's *production* metrics; this is *probing*).

## 3. Goals

1. **Measure latency** (time-to-first-token, tokens/sec, total) per model/provider.
2. Produce **performance profiles** (fast/normal/slow classes) feeding capabilities ([46](./46_CAPABILITY_TAXONOMY.md)) and scoring ([47](./47_SCORING_ALGORITHMS.md)).
3. Offer a **user-triggered speed test** (UI) so users can see and compare provider speed ([06](./06_COMPONENT_LIBRARY.md)).
4. Keep it **cheap and non-intrusive** (small probes, cached results, quota-aware [48](./48_QUOTA_TIER_MANAGEMENT.md)).

### Non-Goals
- Not a rigorous model-quality eval suite (a future extension); quality seeds are curated + lightly probed. Not live production metrics ([51](./51_METRICS.md)).

## 4. Methodology

```
speed probe(model):
  send a small standard prompt → measure:
    ttft (time to first token), tps (tokens/sec), total latency
  repeat K times → take median (robust to outliers)
  respect quota/cooldown (48); use cheap/short probes
quality signal (light): optional small task-set scored heuristically or self-rated;
  seeds capability quality (46) — marked low-confidence until richer eval exists
store: per (model, provider) latency/quality profile with timestamp
```

- Probes are **quota-aware** ([48](./48_QUOTA_TIER_MANAGEMENT.md)) — a speed test must not burn meaningful quota; it uses minimal tokens and is rate-limited.
- Results feed the **latency/cost classes** in the capability taxonomy ([46](./46_CAPABILITY_TAXONOMY.md)) and the `latency`/`quality` factors in scoring ([47](./47_SCORING_ALGORITHMS.md)).

> **OPEN (design):** the exact **probe prompt, K, quality signal, and profile bucketing** are a recovered gap (`PROJECT_ANALYSIS.md` L85). The shape (median-of-K latency probes + light quality seed) is fixed; specifics finalized in implementation.

## 5. User-Facing Speed Test (L52)

- A **Speed Test** action in the provider UI ([06](./06_COMPONENT_LIBRARY.md)) runs probes across configured providers/models and shows a comparison (ttft, tps) — helping users pick or trust auto-selection. Consent-light (it's a normal provider call), quota-aware, and results are cached.

## 6. Performance Profiles (L45)

- A **performance profile** summarizes a model/provider: latency class (fast/normal/slow), typical tps, and a quality tier. Profiles are the digestible output that scoring and the UI consume. They refresh periodically and on user speed-test.

## 7. Directory / Config / Dependencies

```
yonlendirme/benchmark/
  probe.py       # latency probes (ttft/tps/total)
  quality.py     # light quality signal (optional)
  profile.py     # performance profiles → 46/47
  store.py       # cached results (light; 29 options)
```
Probe frequency/K/token budget configurable ([33_CONFIGURATION](./33_CONFIGURATION.md)); quota-aware ([48](./48_QUOTA_TIER_MANAGEMENT.md)). Feeds [46](./46_CAPABILITY_TAXONOMY.md)/[47](./47_SCORING_ALGORITHMS.md); UI [06](./06_COMPONENT_LIBRARY.md).

## 8. Edge Cases

- **Quota-tight:** skip/defer probes; use last-good profiles ([48](./48_QUOTA_TIER_MANAGEMENT.md)).
- **Offline:** only Ollama probed; cloud profiles served from cache.
- **Noisy latency:** median-of-K + outlier trim.
- **Provider down during test:** report unavailable, don't fail the whole test.
- **First run, no profiles:** use conservative seeds ([46](./46_CAPABILITY_TAXONOMY.md)) until probed.

## 9. Failure Recovery / Security / Performance

- Profiles are disposable/rebuildable (re-probe). No secrets stored ([34](./34_API_KEYS.md)). Probes are small + rate-limited so they don't harm performance/quota ([31](./31_PERFORMANCE.md)/[48](./48_QUOTA_TIER_MANAGEMENT.md)).

## 10. Testing Strategy

- Latency computed correctly (ttft/tps/total, median-of-K); quota-aware (probes bounded); offline serves cached profiles; speed-test UI reflects results; profiles feed scoring. See [35_TESTING](./35_TESTING.md).

## 11. Future Extensions

- A real model-quality eval harness (task suites, [35](./35_TESTING.md)); Turkish-specific quality probes (P2); continuous passive latency measurement from live traffic ([51](./51_METRICS.md)); regression alerts on provider slowdowns.

## 12. Anti-Patterns

- Heavy probes that burn quota ([48](./48_QUOTA_TIER_MANAGEMENT.md)).
- Single-sample latency (noisy — use median-of-K).
- Treating light quality seeds as rigorous eval (mark confidence).
- Blocking the UI on a synchronous full benchmark.

## 13. Things That Must Never Happen

1. A speed test burns meaningful provider quota.
2. Latency profiles are single-sample (must be robust).
3. Benchmark data includes secrets.
4. Probing blocks normal operation.

## 14. Relationship With Other Subsystems

Feeds evidence to [46_CAPABILITY_TAXONOMY](./46_CAPABILITY_TAXONOMY.md)/[47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md); consumed indirectly by [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md); quota-aware via [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md); surfaced by [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md); distinct from live [51_METRICS](./51_METRICS.md); rationale [52_ADR_LOG](./52_ADR_LOG.md).

## 15. Migration Considerations

- Methodology shape is stable; probe specifics `OPEN` until implementation. A richer quality eval is additive (PR-18). Profile format versioned; changes trigger re-probe (no data loss).
