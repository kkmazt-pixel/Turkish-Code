# 46 — Capability Taxonomy (Yetenek Taksonomisi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `yonlendirme/capability/`
> **New** ([52_ADR_LOG](./52_ADR_LOG.md) ADR-0005). Recovered gap: `PROJECT_ANALYSIS.md` L44/L81.
> **Related:** [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) · [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md) · [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md)

---

## 1. Purpose

Defines the **capability taxonomy** — the shared vocabulary describing *what a model can do* and *what a task needs*. It is the common language between tasks (which declare a **capability need**) and models (which declare a **capability set**), enabling **model-first, capability-aware routing** ([45](./45_ROUTING_ORCHESTRATION.md), [52](./52_ADR_LOG.md) ADR-0005). Without a stable taxonomy, "best model for the task" is undefinable.

## 2. Scope

The capability dimensions/vocabulary, how models declare capabilities, how tasks declare needs, and the matching contract to the router/scorer. Out of scope: the *scoring math* ([47](./47_SCORING_ALGORITHMS.md)), the *routing flow* ([45](./45_ROUTING_ORCHESTRATION.md)), provider execution ([21](./21_PROVIDER_SYSTEM.md)).

## 3. Goals

1. A **stable, extensible vocabulary** of capabilities (interface-driven, [52](./52_ADR_LOG.md) ADR-0014).
2. Let a task express **what it needs** independent of any model/provider (provider-agnostic, ADR-0012).
3. Let a model express **what it offers** so the scorer can compute capability-fit ([47](./47_SCORING_ALGORITHMS.md)).
4. Support **degradation** (nearest-capability match) when no perfect model exists (PR-7).

### Non-Goals
- Not a benchmark harness ([50](./50_BENCHMARK_SPEEDTEST.md) produces the *evidence*; this doc defines the *dimensions*). Not scoring.

## 4. Capability Dimensions (the vocabulary)

A `CapabilitySet` is a structured value across dimensions. Canonical dimensions (extensible):

| Dimension | Values / type | Meaning |
|---|---|---|
| `role` | chat · embed · rerank · vision · code | primary function |
| `reasoning` | basic · strong · expert | depth of reasoning quality |
| `codeAptitude` | none · basic · strong · expert | code generation/understanding |
| `contextWindow` | int (tokens) | max input the model handles |
| `toolUse` | none · native · structured | tool/function-calling ability ([15](./15_REASONING_ENGINE.md) §6) |
| `vision` | bool | image input |
| `multilingualTR` | poor · ok · strong | **Turkish** quality (P2, [04](./04_TURKISH_DESIGN_LANGUAGE.md)) |
| `latencyClass` | fast · normal · slow | seeded, refined by benchmarks ([50](./50_BENCHMARK_SPEEDTEST.md)) |
| `costClass` | free · cheap · standard · premium | seeded from pricing ([22](./22_PROVIDER_INTEGRATIONS.md)) |
| `maxOutput` | int (tokens) | output limit |
| `streaming` | bool | supports token streaming |

- A **task's capability need** is expressed in the same dimensions (e.g., `{role: chat, reasoning: ≥strong, toolUse: native, multilingualTR: strong, contextWindow: ≥32k}`), with each requirement marked **hard** (must) or **soft** (prefer).
- Turkish quality (`multilingualTR`) is a **first-class** dimension so the router can honor the Turkish-native pillar (P2) when routing to cloud models ([00_PROJECT_VISION](./00_PROJECT_VISION.md), [04](./04_TURKISH_DESIGN_LANGUAGE.md)).

## 5. Declaring Capabilities

- **Models** declare a `CapabilitySet` via the provider adapter's `capabilities(model)` ([21](./21_PROVIDER_SYSTEM.md) §5). Seed values come from provider metadata + curated knowledge; **evidence-based** values (latency, quality) are refined by benchmarks ([50](./50_BENCHMARK_SPEEDTEST.md)).
- **Tasks** declare needs through the reasoning engine/agents ([15](./15_REASONING_ENGINE.md)/[18](./18_AGENT_SYSTEM.md)); a default profile per effort/role is provided so callers needn't over-specify.

## 6. Matching Contract (to router/scorer)

- The router filters candidates by **hard** requirements (must satisfy), then the scorer ([47](./47_SCORING_ALGORITHMS.md)) computes **capability-fit** over soft requirements. No hard-satisfier ⇒ **degrade** to nearest capable + note it (PR-7, [45](./45_ROUTING_ORCHESTRATION.md) §12).

> **OPEN (design):** the concrete **enumerated values, thresholds, and per-model seed data** are a recovered gap (`PROJECT_ANALYSIS.md` L81). This doc fixes the *dimensions*; the *values* are curated during implementation and versioned here (`OPEN` until then).

## 7. Directory Structure

```
yonlendirme/capability/
  taxonomy.py     # dimensions + value enums (this doc)
  need.py         # task capability-need model (hard/soft)
  match.py        # hard-filter + fit inputs for scoring (47)
  seeds/          # per-model seed capability data (curated; refined by 50)
```

## 8–9. Configuration / Dependencies

- Dimension weights/defaults per effort/role are configurable ([33_CONFIGURATION](./33_CONFIGURATION.md)). Depends on [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) (models), feeds [45](./45_ROUTING_ORCHESTRATION.md)/[47](./47_SCORING_ALGORITHMS.md); refined by [50_BENCHMARK_SPEEDTEST](./50_BENCHMARK_SPEEDTEST.md).

## 10. Edge Cases

- **New capability dimension needed:** add it (additive, PR-18); models default to a conservative value until seeded.
- **Provider misreports a capability:** benchmark evidence ([50](./50_BENCHMARK_SPEEDTEST.md)) overrides optimistic seeds.
- **Turkish-sensitive task:** `multilingualTR` becomes a hard requirement so weak-Turkish models are filtered out.
- **No model meets a hard requirement:** degrade to nearest + warn (never silently ignore a hard need without noting it).

## 11. Security / 12. Performance

- Capability data is non-secret metadata (no keys). Matching is O(candidates), trivial vs. inference latency ([31](./31_PERFORMANCE.md)).

## 13. Testing Strategy

- Hard-filter correctness (unqualified models excluded); Turkish-need routing (weak-TR models filtered); degradation path when no perfect match; additive-dimension compatibility. See [35_TESTING](./35_TESTING.md).

## 14. Future Extensions

- Learned capability inference from outcomes; richer domain capabilities (SQL, security-review, refactor); per-language code aptitude.

## 15. Anti-Patterns

- Hardcoding model names in tasks (breaks provider-agnosticism, ADR-0012) — declare *capabilities*, not models.
- Trusting optimistic provider self-reports over benchmark evidence.
- Treating Turkish quality as an afterthought.

## 16. Things That Must Never Happen

1. A task references a specific model/provider instead of a capability (ADR-0012).
2. A hard capability requirement is silently ignored.
3. Turkish-quality is unrepresentable in routing (P2 must be routable).

## 17. Relationship With Other Subsystems

The vocabulary for [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md)/[47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md); populated from [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md)/[22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md); refined by [50_BENCHMARK_SPEEDTEST](./50_BENCHMARK_SPEEDTEST.md); serves the Turkish pillar ([04](./04_TURKISH_DESIGN_LANGUAGE.md)); rationale [52_ADR_LOG](./52_ADR_LOG.md).

## 18. Migration Considerations

- Dimensions are versioned; additions are backward-compatible (PR-18). Seed values evolve as benchmarks accrue. A dimension rename is a tracked migration ([40](./40_DOCUMENTATION_RULES.md)).
