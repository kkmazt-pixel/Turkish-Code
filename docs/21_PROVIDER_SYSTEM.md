# 21 — Provider System (Sağlayıcılar)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 2.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `saglayicilar/`
> **Changed in v2.0** (per [52_ADR_LOG](./52_ADR_LOG.md) ADR-0005/0006/0007/0008): the system is now **model-first** (not provider-first); final provider set is **Gemini, Groq, OpenRouter, NVIDIA NIM** (primary) + **Ollama** (offline fallback); routing/scoring/quota moved to dedicated docs.
> **Related:** [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) · [46_CAPABILITY_TAXONOMY](./46_CAPABILITY_TAXONOMY.md) · [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md) · [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md) · [49_MODEL_CACHE](./49_MODEL_CACHE.md) · [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md) · [34_API_KEYS](./34_API_KEYS.md)

---

## 1. Purpose

Defines **Sağlayıcılar**, the **provider-independent** abstraction over model backends (chat/LLM, embedding, rerank, vision) and the home of the **model-first orchestration** philosophy: turkish.code chooses the **best model for the task**, not a favored provider, and delivers that model through whichever provider offers it. This document owns the provider *interface*, the *model registry*, provider *lifecycle/health*, and the *contracts* to the routing ([45](./45_ROUTING_ORCHESTRATION.md)), scoring ([47](./47_SCORING_ALGORITHMS.md)), quota ([48](./48_QUOTA_TIER_MANAGEMENT.md)), and cache ([49](./49_MODEL_CACHE.md)) subsystems. It replaces the earlier provider-first framing ([52_ADR_LOG](./52_ADR_LOG.md) ADR-0005).

## 2. Scope

The provider interface + roles, the multi-provider registry/manager, the final provider set, provider health/lifecycle, streaming, and the boundaries to routing/scoring/quota/cache/secrets. Out of scope: the **router decision logic** ([45](./45_ROUTING_ORCHESTRATION.md)), **capability taxonomy** ([46](./46_CAPABILITY_TAXONOMY.md)), **scoring formulas** ([47](./47_SCORING_ALGORITHMS.md)), **quota/tier** ([48](./48_QUOTA_TIER_MANAGEMENT.md)), **model cache** ([49](./49_MODEL_CACHE.md)), **per-provider integration specifics** ([22](./22_PROVIDER_INTEGRATIONS.md)), and **key handling** ([34](./34_API_KEYS.md)).

## 3. Goals

1. **Provider-independent architecture** (ADR-0002): the rest of the system never depends on a specific vendor; agents are **provider-agnostic** (ADR-0012, [18](./18_AGENT_SYSTEM.md)).
2. **Model-first** (ADR-0005): request a *capability*, get the *best model*; providers are interchangeable delivery channels.
3. **Extensible with minimal change** (ADR-0014): adding a provider = implement one interface + register; **no core changes** (SOLID/DI, [36](./36_CODING_STANDARDS.md)).
4. **Resilient** (ADR-0009): smart failover, retry, timeout, cooldown across providers.
5. **Cost/quota aware** (ADR-0006): expose the signals routing needs to preserve quota and quality ([48](./48_QUOTA_TIER_MANAGEMENT.md)).

### Non-Goals
- Not the router itself ([45](./45_ROUTING_ORCHESTRATION.md), a consumer). Not scoring/quota logic ([47](./47_SCORING_ALGORITHMS.md)/[48](./48_QUOTA_TIER_MANAGEMENT.md)). Not secret storage ([34](./34_API_KEYS.md)). Not the embedding pipeline ([14](./14_EMBEDDINGS.md)).

## 4. Final Provider Architecture (ADR-0007/0008)

| Provider | Kind | Role in the architecture | Notes |
|---|---|---|---|
| **Gemini** | cloud (primary) | chat/vision/(embed) | Google models via API. |
| **Groq** | cloud (primary) | chat | Very low-latency inference. |
| **OpenRouter** | cloud (primary) | chat/(embed) | Aggregator → many models behind one provider. |
| **NVIDIA NIM** | cloud/self-host (primary) | chat/embed/rerank/vision | Reintroduced after earlier rejection ([52](./52_ADR_LOG.md) ADR-0007); **one of four primaries, not flagship**. |
| **Ollama** | local (fallback) | chat/embed | **Offline fallback**, not a primary provider ([32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md), ADR-0010). |

- **Cloud-primary, offline-fallback** (ADR-0010): the four primaries are the normal path; Ollama provides the local/offline resilience path — see [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md).
- **OpenRouter** is special: it is itself a multi-model aggregator, so the model registry expands it into many concrete models the router can pick among ([45](./45_ROUTING_ORCHESTRATION.md)).
- New providers may be added (via the interface, ADR-0014) or by plugins ([23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md)). Per-provider details: [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md).

## 5. Provider Interface (single responsibility, ADR-0014)

Each provider is a **single-responsibility** adapter implementing one interface (SOLID, [36](./36_CODING_STANDARDS.md)):

```
Provider {
  id: string                       // "gemini" | "groq" | "openrouter" | "nvidia-nim" | "ollama"
  kind: cloud | local
  tierInfo: { tier, quotaLimits }  // for quota/tier routing (48)
  listModels() -> [ModelInfo]      // feeds the registry + model cache (49)
  # capability calls (async, streaming where applicable):
  chat(model, messages, tools?, opts) -> stream<delta> | result
  embed(model, texts, kind) -> [vector]     // semantics: doc 14
  rerank(model, query, candidates) -> [scored]
  health() -> HealthStatus         // up | degraded | cooling_down | down (45/48)
  capabilities(model) -> CapabilitySet     // maps to the taxonomy (46)
}

ModelInfo {
  id, providerId, roles:[chat|embed|rerank|vision],
  capabilities: CapabilitySet,     // (46) — what the model is good at
  contextWindow, pricing?, tier?,  // pricing/tier drive cost/quota routing (48)
  latencyProfile?, quality?        // seed values; refined by benchmarks (50)
}
```

- The interface is **capability-oriented**: callers ask for a capability (via the router), never for a vendor. Model non-determinism is confined here (PR-15); inputs/outputs recorded upstream ([15](./15_REASONING_ENGINE.md), [26](./26_TIMELINE.md)).
- Adding a provider = implement `Provider`, declare its models' capabilities, register it. Nothing else changes (ADR-0014).

## 6. Model Registry & Manager

- The **provider manager** (ADR-0003) registers providers, enumerates their models via `listModels()`, and maintains the **unified model registry** — a flat, provider-independent catalog of `ModelInfo` the router selects from.
- The registry is backed by the **24-hour model cache** ([49_MODEL_CACHE](./49_MODEL_CACHE.md)) so enumeration isn't repeated per run; it refreshes per the cache policy.
- The manager tracks **health** per provider (up/degraded/cooling_down/down) and surfaces it to the router ([45](./45_ROUTING_ORCHESTRATION.md)) and the UI ([06](./06_COMPONENT_LIBRARY.md) provider status).
- **Model-first selection** is delegated to the **router** ([45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md)); the provider system merely *supplies* the registry, capabilities, health, tier/quota signals, and the execution calls. (This separation is the crux of ADR-0005: the provider layer no longer "chooses" — it *offers*.)

## 7. Relationship to Routing / Scoring / Quota / Cache (Boundaries)

The provider system provides raw material; four sibling docs consume it:
- **Routing/Orchestration** ([45](./45_ROUTING_ORCHESTRATION.md)) — picks the model per request (model-first, dynamic), orchestrates failover/retry/timeout/cooldown.
- **Capability Taxonomy** ([46](./46_CAPABILITY_TAXONOMY.md)) — the vocabulary `capabilities()` speaks.
- **Scoring** ([47](./47_SCORING_ALGORITHMS.md)) — provider score + model score used by the router.
- **Quota & Tier** ([48](./48_QUOTA_TIER_MANAGEMENT.md)) — quota tracking/persistence + quota-preserving routing + quality-under-exhaustion.
- **Model Cache** ([49](./49_MODEL_CACHE.md)) — caches `listModels()`.

This keeps the provider system a **thin, single-responsibility layer** (ADR-0014); intelligence lives in the router.

## 8. Streaming, Cancellation, Budgets

- All chat providers expose token streaming; deltas surface as reasoning/token notifications ([10](./10_IPC.md), [15](./15_REASONING_ENGINE.md)).
- Cancellation ([10](./10_IPC.md) `$/cancel`) aborts the active provider call.
- Per-call token limits and model preference come from the **compute-depth effort dial**; provider/model cost preference comes from the **cost/quota dial** — the two dials of [17_EFFORT_MODES](./17_EFFORT_MODES.md) (ADR-0011).

## 9. Health, Failover & Cooldown (summary; detail in [45](./45_ROUTING_ORCHESTRATION.md))

- Each provider reports **health**; on error/rate-limit/timeout a provider enters **cooldown** ([48](./48_QUOTA_TIER_MANAGEMENT.md)) and the router fails over to the next-best *model* (which may be on another provider) — **smart failover**, not simple static failover (ADR-0009).
- Retry uses bounded backoff; timeouts are per-call; cooldown prevents hammering a degraded provider. Ollama is the **last-resort offline fallback** when all cloud providers are unavailable ([32](./32_OFFLINE_FIRST.md)).

## 10. Directory Structure

```
saglayicilar/
  provider.py       # Provider interface + ModelInfo/CapabilitySet types
  manager.py        # registry + provider lifecycle + health tracking
  gemini/           # per-provider adapters (see doc 22)
  groq/
  openrouter/
  nvidia_nim/
  ollama/           # local/offline fallback
  stream.py         # uniform streaming/cancellation
# routing (45), scoring (47), quota (48), cache (49) live in their own modules
```

## 11. Key Handling (Boundary)

Cloud providers need API keys. Keys are handled **lightly** (ADR-0010): kept **outside source code** in configuration/env, loaded at startup, used to authenticate provider calls. This is a deliberate simplification from the earlier heavy OS-keychain vault. Details + the rationale for *not* using a heavy keyring: [34_API_KEYS](./34_API_KEYS.md).

## 12. Configuration

- Configured providers, enabled/disabled state, per-provider keys (via [34](./34_API_KEYS.md)), per-role model pins, the **cost/quota mode** default ([17](./17_EFFORT_MODES.md)), routing policy hints, and the model-cache TTL ([49](./49_MODEL_CACHE.md)) live in config ([33_CONFIGURATION](./33_CONFIGURATION.md)). Default: the four primaries enabled where a key is present, Ollama as fallback.

## 13. Dependencies

- [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md), [46_CAPABILITY_TAXONOMY](./46_CAPABILITY_TAXONOMY.md), [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md), [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md), [49_MODEL_CACHE](./49_MODEL_CACHE.md), [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md), [34_API_KEYS](./34_API_KEYS.md), [14_EMBEDDINGS](./14_EMBEDDINGS.md) (embed/rerank consumers), [17_EFFORT_MODES](./17_EFFORT_MODES.md), [51_METRICS](./51_METRICS.md).

## 14. Edge Cases

- **No cloud key configured / all cloud down:** fall back to **Ollama** (offline path, [32](./32_OFFLINE_FIRST.md)); if Ollama absent too, a typed error ([38](./38_ERROR_HANDLING.md)) with remediation.
- **OpenRouter model list changes:** re-expanded on cache refresh ([49](./49_MODEL_CACHE.md)).
- **Provider rate-limit/quota hit:** cooldown + failover; quota tracked/persisted ([48](./48_QUOTA_TIER_MANAGEMENT.md)).
- **Capability mismatch** (no model has the requested capability): router degrades to the closest capable model ([45](./45_ROUTING_ORCHESTRATION.md)/[47](./47_SCORING_ALGORITHMS.md)).
- **Embedding model coherence:** the registry records embed model id/dim; the vector store must use the same ([14](./14_EMBEDDINGS.md) §9).
- **Provider returns malformed/broken stream:** typed error → router failover.
- **New provider added by plugin:** validated + registered like a built-in ([23](./23_PLUGIN_SYSTEM.md)).

## 15. Failure Recovery

- Provider failures are isolated per call; the router fails over ([45](./45_ROUTING_ORCHESTRATION.md)); a run resumes from its last checkpoint if a provider dies mid-stream ([28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md)). Local (Ollama) runtime crashes are isolated to a worker ([09](./09_PYTHON_BACKEND.md)).

## 16. Security

- Keys are kept outside source code and out of logs ([34](./34_API_KEYS.md)/[39](./39_LOGGING.md), redaction). Provider responses (model output) are untrusted downstream ([15](./15_REASONING_ENGINE.md)). Cloud endpoints are validated (no arbitrary host injection). Note: v2.0 intentionally does **not** carry the earlier heavy privacy/egress-choke apparatus (ADR-0010); see [30_SECURITY](./30_SECURITY.md) for the current, slimmer posture.

## 17. Performance

- Prefer low-latency providers per the cost/quota mode; keep the model cache warm ([49](./49_MODEL_CACHE.md)); stream early; batch embeds ([14](./14_EMBEDDINGS.md)). Provider health + latency profiles feed routing ([45](./45_ROUTING_ORCHESTRATION.md)/[50](./50_BENCHMARK_SPEEDTEST.md)). Metrics in [51_METRICS](./51_METRICS.md)/[31_PERFORMANCE](./31_PERFORMANCE.md).

## 18. Testing Strategy

- **Interface conformance:** every provider passes the same capability suite (chat/embed/rerank/stream/cancel/health).
- **Provider-independence:** the system runs identically swapping providers (no core change) — proves ADR-0002/0014.
- **Failover/cooldown:** simulated provider failure → smart failover to next-best model, cooldown honored (ADR-0009).
- **Offline fallback:** all cloud disabled → Ollama serves ([32](./32_OFFLINE_FIRST.md)).
- **Registry/cache:** model enumeration cached 24h, refreshes correctly ([49](./49_MODEL_CACHE.md)). See [35_TESTING](./35_TESTING.md).

## 19. Future Extensions

- More providers via plugins ([23](./23_PLUGIN_SYSTEM.md)); provider-side speculative decoding/cascades; richer latency/quality profiles from live benchmarks ([50](./50_BENCHMARK_SPEEDTEST.md)); a LAN "remote local" provider.

## 20. Examples

- Cost/quota mode = **Economy**, task needs a capable chat model: router asks the registry for chat-capable models, scores them ([47](./47_SCORING_ALGORITHMS.md)) preferring cheaper/quota-preserving options ([48](./48_QUOTA_TIER_MANAGEMENT.md)), picks e.g. a Groq or OpenRouter model; if it rate-limits → cooldown + failover to the next-best; if all cloud is down → Ollama. The **agent never knew which provider** served it (ADR-0012).

## 21. Anti-Patterns

- Provider-first selection ("use Groq, then pick a model") — rejected (ADR-0005); ask for a capability, let the router pick.
- Baking a vendor SDK/format into reasoning/agent code (must sit behind the interface).
- A core feature depending on one specific provider.
- Putting routing/scoring/quota logic in the provider layer (belongs in [45](./45_ROUTING_ORCHESTRATION.md)/[47](./47_SCORING_ALGORITHMS.md)/[48](./48_QUOTA_TIER_MANAGEMENT.md)).
- Re-enumerating models every run (use the cache).

## 22. Things That Must Never Happen

1. The system becomes coupled to a single provider (breaks ADR-0002).
2. Adding a provider requires changing core/agent code (breaks ADR-0014).
3. An agent selects a provider directly (breaks provider-agnostic agents, ADR-0012).
4. Routing/scoring/quota logic leaks into the provider adapters.
5. A cloud outage with Ollama available still hard-fails (must fall back).

## 23. Relationship With Other Subsystems

Supplies models to [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) (which serves [15](./15_REASONING_ENGINE.md)/[16](./16_COUNCIL_MODE.md)/[18](./18_AGENT_SYSTEM.md)/[14](./14_EMBEDDINGS.md)); scored by [47](./47_SCORING_ALGORITHMS.md); quota-governed by [48](./48_QUOTA_TIER_MANAGEMENT.md); cached by [49](./49_MODEL_CACHE.md); per-provider detail in [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md); keys via [34_API_KEYS](./34_API_KEYS.md); offline fallback per [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md); history/rationale in [52_ADR_LOG](./52_ADR_LOG.md).

## 24. Migration Considerations

- **v1.0 → v2.0** (this change): provider-first → model-first; provider set changed to Gemini/Groq/OpenRouter/NVIDIA NIM + Ollama fallback; routing/scoring/quota/cache extracted to [45](./45_ROUTING_ORCHESTRATION.md)–[49](./49_MODEL_CACHE.md); heavy keyring/privacy removed (ADR-0010). The provider *interface* is versioned; adding providers stays additive (ADR-0014). See [52_ADR_LOG](./52_ADR_LOG.md) for the full history.
