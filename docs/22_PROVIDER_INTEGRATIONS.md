# 22 — Provider Integrations (Sağlayıcı Entegrasyonları)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 2.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `saglayicilar/{gemini,groq,openrouter,nvidia_nim,ollama}/`
> **Replaces v1.0 "22 — NVIDIA Integration".** Per [52_ADR_LOG](./52_ADR_LOG.md) ADR-0007/0008: NVIDIA NIM is **one of four primary providers**, **not** the flagship/sovereign path; final set = **Gemini, Groq, OpenRouter, NVIDIA NIM** (primary) + **Ollama** (offline fallback).
> **Related:** [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) · [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) · [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md) · [34_API_KEYS](./34_API_KEYS.md) · [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md)

---

## 1. Purpose

Documents the **concrete integration** of each provider that implements the provider interface ([21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) §5): identity, models/roles, auth, tier/quota characteristics, and integration specifics. It is the per-provider companion to the provider-independent system doc. **No provider here is a "flagship"** — they are peer delivery channels for models, selected by the model-first router ([45](./45_ROUTING_ORCHESTRATION.md), [52](./52_ADR_LOG.md) ADR-0005).

## 2. Scope

Per-provider integration details for **Gemini, Groq, OpenRouter, NVIDIA NIM** (primary) and **Ollama** (offline fallback): endpoints/SDK shape, models, roles, auth, tier/quota, and quirks. Out of scope: the provider abstraction ([21](./21_PROVIDER_SYSTEM.md)), routing/scoring/quota logic ([45](./45_ROUTING_ORCHESTRATION.md)/[47](./47_SCORING_ALGORITHMS.md)/[48](./48_QUOTA_TIER_MANAGEMENT.md)), key storage policy ([34](./34_API_KEYS.md)).

## 3. Goals

1. Make each provider **implementable** from this doc + the interface ([21](./21_PROVIDER_SYSTEM.md) §5).
2. Capture provider-specific **quirks** (auth, rate-limits, model naming, streaming) so adapters are correct.
3. Keep every provider a **single-responsibility adapter** (SOLID, [52](./52_ADR_LOG.md) ADR-0014) — no shared special-casing leaking into the core.

### Non-Goals
- Not routing/scoring/quota policy. Not a marketing comparison. NVIDIA is **not** presented as special.

## 4. Provider Roster (summary)

| Provider | Kind | Primary roles | Auth | Notes |
|---|---|---|---|---|
| **Gemini** | cloud (primary) | chat, vision, embed | API key | Google GenAI models. |
| **Groq** | cloud (primary) | chat | API key | Very low latency; good for fast/Performance routing. |
| **OpenRouter** | cloud (primary) | chat, (embed) | API key | **Aggregator** → many models under one provider; expanded into the registry ([21](./21_PROVIDER_SYSTEM.md) §6). |
| **NVIDIA NIM** | cloud / self-host (primary) | chat, embed, rerank, vision | API key (or local endpoint) | Reintroduced (ADR-0007); one of four, **not** flagship/sovereign. |
| **Ollama** | local (fallback) | chat, embed | none (local) | **Offline fallback** only ([32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md)). |

## 5. Per-Provider Integration

### 5.1 Gemini (primary)
- **Interface:** Google GenAI HTTP API; chat + vision + embeddings.
- **Models:** enumerated via the API (or a curated list) → `listModels()`; capabilities seeded per model ([46](./46_CAPABILITY_TAXONOMY.md)).
- **Auth:** API key, outside source code ([34](./34_API_KEYS.md)).
- **Tier/quota:** per-key rate/token limits → tracked ([48](./48_QUOTA_TIER_MANAGEMENT.md)).
- **Quirks:** streaming format; safety-setting parameters; vision input encoding.

### 5.2 Groq (primary)
- **Interface:** OpenAI-compatible chat completions API (very fast).
- **Models:** the Groq-hosted set → `listModels()`.
- **Auth:** API key ([34](./34_API_KEYS.md)).
- **Tier/quota:** aggressive rate limits on free tiers → cooldown-prone ([48](./48_QUOTA_TIER_MANAGEMENT.md)); its **latency advantage** makes it a strong pick under Performance mode ([47](./47_SCORING_ALGORITHMS.md)).
- **Quirks:** OpenAI-compatible → can share a base adapter; low ttft is its differentiator (measured by [50](./50_BENCHMARK_SPEEDTEST.md)).

### 5.3 OpenRouter (primary, aggregator)
- **Interface:** OpenAI-compatible; a **gateway** to many upstream models.
- **Models:** `listModels()` returns a **large set**; each becomes a registry entry ([21](./21_PROVIDER_SYSTEM.md) §6). Capabilities/pricing vary per underlying model.
- **Auth:** API key ([34](./34_API_KEYS.md)).
- **Tier/quota:** per-key + per-underlying-model limits; pricing varies widely → strong signal for cost/quota routing ([48](./48_QUOTA_TIER_MANAGEMENT.md)).
- **Quirks:** the model list is large and changes → relies on the **24h model cache** ([49_MODEL_CACHE](./49_MODEL_CACHE.md)); dedupe against models also offered directly (e.g., a Gemini model via OpenRouter vs direct Gemini).

### 5.4 NVIDIA NIM (primary — reintroduced, not flagship)
- **Interface:** NIM (NVIDIA Inference Microservice) — OpenAI-compatible endpoints; **cloud (NVIDIA API) or self-hosted** on the user's GPU.
- **Models:** NIM-served models incl. strong **embedding/rerank** (NeMo Retriever) → `listModels()`; NVIDIA is a good option for embed/rerank roles ([14_EMBEDDINGS](./14_EMBEDDINGS.md)).
- **Auth:** API key for the NVIDIA-hosted path; a **local endpoint** (loopback) for self-hosted NIM — no key, no egress in that case.
- **Tier/quota:** per-key limits for hosted; effectively unlimited for self-hosted (bounded by GPU).
- **Status note:** NVIDIA NIM was **earlier rejected then reintroduced** ([52_ADR_LOG](./52_ADR_LOG.md) ADR-0007). It is treated **exactly like the other primaries** — the router picks it only when it scores best ([47](./47_SCORING_ALGORITHMS.md)); there is **no** special "sovereign/offline-first" framing anymore (that framing was superseded, ADR-0010).
- **Quirks:** self-hosted NIM binds loopback only (if used); GPU detection for the self-host path; NeMo Retriever for embeddings ([14](./14_EMBEDDINGS.md)).

### 5.5 Ollama (offline fallback — not primary)
- **Interface:** local Ollama HTTP API (loopback); chat + embeddings.
- **Models:** locally installed models → `listModels()`; available with **no network**.
- **Auth:** none (local).
- **Role:** the **offline/last-resort fallback** ([32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md), ADR-0008/0010). The router uses Ollama when cloud providers are unavailable/exhausted ([45](./45_ROUTING_ORCHESTRATION.md) §6), or when the user explicitly prefers local. It is **not** a primary provider and is **not** the product's headline identity.
- **Quirks:** model quality/size depends on the user's machine; latency/quality profiles from [50](./50_BENCHMARK_SPEEDTEST.md).

## 6. Adding a New Provider

Implement the `Provider` interface ([21](./21_PROVIDER_SYSTEM.md) §5), declare its models' capabilities ([46](./46_CAPABILITY_TAXONOMY.md)) and tier info ([48](./48_QUOTA_TIER_MANAGEMENT.md)), add auth via config ([34](./34_API_KEYS.md)), register it. **No core changes** (ADR-0014). Add a §5.x here documenting its quirks. Plugins may contribute providers ([23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md)).

## 7. Directory Structure

```
saglayicilar/
  gemini/     groq/     openrouter/     nvidia_nim/     ollama/
  base_openai_compat.py   # shared adapter for OpenAI-compatible providers (groq/openrouter/nim)
```

## 8. Configuration

- Each provider: enabled flag + API key ref ([34](./34_API_KEYS.md)) + optional endpoint (self-host NIM / Ollama host). Defaults: primaries enabled where a key exists; Ollama enabled as fallback if present. See [33_CONFIGURATION](./33_CONFIGURATION.md).

## 9. Dependencies

- [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) (interface), [34_API_KEYS](./34_API_KEYS.md) (keys), [46_CAPABILITY_TAXONOMY](./46_CAPABILITY_TAXONOMY.md)/[48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md)/[49_MODEL_CACHE](./49_MODEL_CACHE.md)/[50_BENCHMARK_SPEEDTEST](./50_BENCHMARK_SPEEDTEST.md), [14_EMBEDDINGS](./14_EMBEDDINGS.md) (NVIDIA/others as embedders), [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md) (Ollama).

## 10. Edge Cases

- **OpenRouter duplicates a direct provider's model:** dedupe/prefer per policy ([45](./45_ROUTING_ORCHESTRATION.md)); pricing may differ.
- **Groq/free-tier rate limit:** cooldown + failover ([48](./48_QUOTA_TIER_MANAGEMENT.md)).
- **NVIDIA self-host but no GPU:** fall back to NVIDIA hosted (with key) or other providers; ultimately Ollama/other local.
- **Ollama not installed + offline:** no models → typed error with guidance to install a local model ([32](./32_OFFLINE_FIRST.md)/[38](./38_ERROR_HANDLING.md)).
- **Provider API version change:** absorbed in that provider's adapter only (single responsibility, ADR-0014).

## 11. Failure Recovery / Security / Performance

- Provider failures isolate to their adapter; router fails over ([45](./45_ROUTING_ORCHESTRATION.md)). Keys are light-handled + never logged ([34](./34_API_KEYS.md)/[39](./39_LOGGING.md)); self-hosted NIM/Ollama bind loopback only. Latency/cost feed routing ([47](./47_SCORING_ALGORITHMS.md)/[50](./50_BENCHMARK_SPEEDTEST.md)). See [31_PERFORMANCE](./31_PERFORMANCE.md).

## 12. Testing Strategy

- Each adapter passes the shared provider conformance suite ([21](./21_PROVIDER_SYSTEM.md) §18); OpenAI-compatible base shared by Groq/OpenRouter/NIM; Ollama-offline path; OpenRouter list expansion + cache ([49](./49_MODEL_CACHE.md)); NVIDIA embed/rerank ([14](./14_EMBEDDINGS.md)). See [35_TESTING](./35_TESTING.md).

## 13. Future Extensions

- More providers via plugins ([23](./23_PLUGIN_SYSTEM.md)); provider-native tool-calling nuances; regional endpoints; a curated OpenRouter model allowlist.

## 14. Anti-Patterns

- Treating any provider as "flagship"/special in the core (all are peers, ADR-0005/0007).
- Provider-specific logic leaking outside its adapter (breaks single-responsibility).
- Re-enumerating OpenRouter every run (use the cache).
- A key in logs/source ([34](./34_API_KEYS.md)).

## 15. Things That Must Never Happen

1. A provider gets special "flagship/sovereign" treatment in core routing.
2. Provider-specific code leaks into the core (must stay in its adapter).
3. A key is logged or committed.
4. Ollama is presented/used as a *primary* provider (it is the offline fallback).

## 16. Relationship With Other Subsystems

Implements [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md); selected by [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) via [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md); metered by [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md); cached by [49_MODEL_CACHE](./49_MODEL_CACHE.md); benchmarked by [50_BENCHMARK_SPEEDTEST](./50_BENCHMARK_SPEEDTEST.md); embeddings via [14_EMBEDDINGS](./14_EMBEDDINGS.md); keys via [34_API_KEYS](./34_API_KEYS.md); Ollama offline path [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md); history [52_ADR_LOG](./52_ADR_LOG.md).

## 17. Migration Considerations

- **v1.0 (NVIDIA-only) → v2.0 (five-provider catalog):** NVIDIA demoted from flagship to one-of-four; Gemini/Groq/OpenRouter added; Ollama as fallback. Each provider is an independent adapter; adding/removing one is additive (ADR-0014). Provider API changes are adapter-local (PR-8).
