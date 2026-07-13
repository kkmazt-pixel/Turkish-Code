# 47 — Scoring Algorithms (Puanlama Algoritmaları)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `yonlendirme/scoring/`
> **New** ([52_ADR_LOG](./52_ADR_LOG.md) ADR-0005). Recovered gap: `PROJECT_ANALYSIS.md` L41/L42/L82.
> **Related:** [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) · [46_CAPABILITY_TAXONOMY](./46_CAPABILITY_TAXONOMY.md) · [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md) · [17_EFFORT_MODES](./17_EFFORT_MODES.md)

---

## 1. Purpose

Defines how turkish.code **scores providers and models** so the router ([45](./45_ROUTING_ORCHESTRATION.md)) can pick the best one. There are two scores — **model score** (how good is this model for *this task*) and **provider score** (how healthy/available/quota-rich is its provider right now) — combined and reweighted by the user's **cost/quota mode** ([17](./17_EFFORT_MODES.md)). Scoring is what turns "model-first" ([52](./52_ADR_LOG.md) ADR-0005) from a slogan into a computation.

## 2. Scope

The model-score and provider-score factors, the cost-mode weighting, the combination formula, and how scores feed the router. Out of scope: candidate generation/failover ([45](./45_ROUTING_ORCHESTRATION.md)), capability vocabulary ([46](./46_CAPABILITY_TAXONOMY.md)), quota mechanics ([48](./48_QUOTA_TIER_MANAGEMENT.md)), benchmark data collection ([50](./50_BENCHMARK_SPEEDTEST.md)).

## 3. Goals

1. Rank candidate models so **best-model-for-task** is a number, not a guess.
2. Make the ranking **mode-sensitive** (Performance vs Balanced vs Economy, [17](./17_EFFORT_MODES.md) ADR-0011).
3. Fold in **live** provider signals (health, quota, cooldown) so scoring is dynamic (ADR-0004).
4. Be **explainable** — every score decomposes into named factors (recorded, [26](./26_TIMELINE.md)/[51](./51_METRICS.md)).

### Non-Goals
- Not the router loop. Not quota bookkeeping ([48](./48_QUOTA_TIER_MANAGEMENT.md), which *provides* the quota factor).

## 4. Model Score (per candidate model, per task)

`modelScore = Σ (weight_f × factor_f)` over factors:

| Factor | Source | Meaning |
|---|---|---|
| `capabilityFit` | [46](./46_CAPABILITY_TAXONOMY.md) | how well the model's capabilities meet the task's soft needs |
| `quality` | seed + benchmarks ([50](./50_BENCHMARK_SPEEDTEST.md)) | task-relevant answer quality |
| `turkishQuality` | [46](./46_CAPABILITY_TAXONOMY.md) `multilingualTR` | Turkish fidelity (P2 weight, [04](./04_TURKISH_DESIGN_LANGUAGE.md)) |
| `latency` | benchmarks/live ([50](./50_BENCHMARK_SPEEDTEST.md)) | speed (higher = faster) |
| `cost` | pricing ([22](./22_PROVIDER_INTEGRATIONS.md)) | cheaper = higher (inverted) |
| `contextFit` | [46](./46_CAPABILITY_TAXONOMY.md) | context window vs task size |

## 5. Provider Score (per provider, live)

`providerScore = f(health, quotaHeadroom, cooldownState, reliability)`:

| Factor | Source | Effect |
|---|---|---|
| `health` | [21](./21_PROVIDER_SYSTEM.md) | degraded/down → sharply lower |
| `quotaHeadroom` | [48](./48_QUOTA_TIER_MANAGEMENT.md) | near-exhaustion → lower (preserve quota) |
| `cooldownState` | [48](./48_QUOTA_TIER_MANAGEMENT.md) | cooling-down → excluded/near-zero |
| `reliability` | [51](./51_METRICS.md) | historical success rate |

## 6. Combination & Cost-Mode Weighting

```
finalScore(model) = modelScore(model) × providerScore(providerOf(model))   [live gating]
weights come from the COST/QUOTA MODE (17, ADR-0011):
  Performance → high weight on quality/turkishQuality/latency; cost/quota nearly ignored
  Balanced    → even weighting
  Economy     → high weight on cost + quotaHeadroom; quality still floored (never terrible)
```

- The **compute-depth effort dial** ([17](./17_EFFORT_MODES.md)) separately sets token budgets and may raise the *minimum quality floor* (e.g., Derin/Maksimum won't pick a weak model even in Economy). The two dials are orthogonal (ADR-0011).
- **Quality floor:** Economy reduces cost but never below a task-appropriate quality floor — this is how quota-preservation (ADR-0006) avoids collapsing quality ([48](./48_QUOTA_TIER_MANAGEMENT.md)).

> **OPEN (design):** the exact **weights, factor normalizations, and the quality floor** are a recovered gap (`PROJECT_ANALYSIS.md` L82). This doc fixes the *factors and shape*; the *coefficients* are tuned during implementation, versioned here, and validated by benchmarks ([50](./50_BENCHMARK_SPEEDTEST.md)).

## 7. Explainability

Every score is returned as a **decomposition** (factor → contribution), recorded in the routing decision ([45](./45_ROUTING_ORCHESTRATION.md) §4 step 4) and available to the UI ("why this model") and metrics ([51](./51_METRICS.md)). No opaque black-box scores (PR-11).

## 8. Directory / Config / Dependencies

```
yonlendirme/scoring/
  model_score.py · provider_score.py · combine.py · weights.py (per mode)
```
Weights/floors configurable ([33_CONFIGURATION](./33_CONFIGURATION.md)). Depends on [46](./46_CAPABILITY_TAXONOMY.md), [48](./48_QUOTA_TIER_MANAGEMENT.md), [50](./50_BENCHMARK_SPEEDTEST.md), [22](./22_PROVIDER_INTEGRATIONS.md); feeds [45](./45_ROUTING_ORCHESTRATION.md).

## 9. Edge Cases

- **All scores low** (bad options): still pick the highest + warn (PR-7); never fail if a candidate exists.
- **Tie:** deterministic tie-break (reliability, then lower cost, then stable id) for reproducibility (PR-15).
- **Missing benchmark data:** use conservative seeds ([46](./46_CAPABILITY_TAXONOMY.md)); flag low confidence.
- **Economy vs quality-floor conflict:** floor wins (quality preserved, ADR-0006).
- **Cooling-down provider:** effectively excluded via near-zero providerScore.

## 10. Failure Recovery / Security / Performance

- Scoring is pure/deterministic given inputs (PR-15) → reproducible, easy to recover/replay. No secrets involved. O(candidates) cost, negligible vs inference ([31](./31_PERFORMANCE.md)).

## 11. Testing Strategy

- Mode reweighting changes the winner as expected (Performance vs Economy).
- Quality floor holds under Economy (no terrible model chosen).
- Determinism/tie-break reproducible.
- Cooling-down/quota-low providers deprioritized.
- Score decomposition present + sums correctly. See [35_TESTING](./35_TESTING.md).

## 12. Future Extensions

- Learned weights from outcome feedback (bandit); per-task-type weight profiles; confidence-aware scoring.

## 13. Anti-Patterns

- Opaque scores with no decomposition (breaks explainability).
- Cost mode that ignores the quality floor (collapses quality — violates ADR-0006).
- Static per-provider preference baked into scoring (must be dynamic).
- Non-deterministic tie-breaks.

## 14. Things That Must Never Happen

1. A score is unexplainable (must decompose into named factors).
2. Economy mode selects a below-floor-quality model.
3. Scoring ignores live health/quota/cooldown (must be dynamic).
4. Non-reproducible selection for identical inputs.

## 15. Relationship With Other Subsystems

Consumed by [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md); uses [46_CAPABILITY_TAXONOMY](./46_CAPABILITY_TAXONOMY.md), [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md), [50_BENCHMARK_SPEEDTEST](./50_BENCHMARK_SPEEDTEST.md), [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md); weighted by [17_EFFORT_MODES](./17_EFFORT_MODES.md); explained in [51_METRICS](./51_METRICS.md); rationale [52_ADR_LOG](./52_ADR_LOG.md).

## 16. Migration Considerations

- Factors are stable; coefficients/floors are versioned config, tuned over time (OPEN until first tuning). Learned scoring is additive behind the same factor interface (PR-8/PR-18).
