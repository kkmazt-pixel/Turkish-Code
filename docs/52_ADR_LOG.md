# 52 — Architecture Decision Record Log (Mimari Karar Günlüğü)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth for *why* decisions were made.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Source of truth for history:** `PROJECT_ANALYSIS.md` (distilled from the founder's real engineering conversations).
> **Related:** [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) · [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) · [43_NON_GOALS](./43_NON_GOALS.md) · [00_PROJECT_VISION](./00_PROJECT_VISION.md) · [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md)

---

## 0. Purpose & The Chronological-Reading Rule (READ FIRST)

This document records **architectural decisions and their evolution** — including **rejected** ideas and, crucially, **ideas that were rejected and later reintroduced**. It exists because the recovered history (`PROJECT_ANALYSIS.md`) is a **chronological engineering history, not a flat specification.**

> **THE RULE:** When reading `PROJECT_ANALYSIS.md` (or this log), **follow the *latest* chronological decision.** Do **not** assume the first occurrence — or the presence of an item under "Rejected Ideas" — is final. A decision can be reversed later.
>
> **Canonical example:** `PROJECT_ANALYSIS.md` lists **NVIDIA NIM under "Rejected Ideas"**, yet NVIDIA NIM was **reintroduced later** and is now a **primary provider** ([ADR-0007](#adr-0007--reintroduce-nvidia-nim-as-a-primary-provider)). The "Rejected Ideas" list is *point-in-time*, not final.

Every ADR below has a **Status** (Accepted / Superseded / Reversed / Rejected / Rejected-then-Reversed) and, where relevant, the ADR that superseded it. This is how we never fall into the "first occurrence = final" trap again.

---

## 1. How To Use This Log

- Each ADR: an id, a title, status, context, decision, consequences, and the docs that implement it.
- ADRs are **append-only**; a change of mind is a **new ADR** that supersedes an old one (the old one is marked, never deleted) — mirroring the Timeline's immutability ethos ([26_TIMELINE](./26_TIMELINE.md)).
- The [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md) links here as the *why-history* authority; subsystem docs describe the *current* state, this log describes *how we got there*.

---

## 2. Architecture Evolution Timeline (the 6 stages)

Recovered from `PROJECT_ANALYSIS.md` §"Architecture Evolution". The provider/LLM layer evolved through six stages; the **final** state is stage 6:

```
1. Static model pools ....................... (ADR-0001, Superseded)
2. Multi-provider abstraction ............... (ADR-0002, Accepted, refined)
3. Provider manager ......................... (ADR-0003, Accepted, refined)
4. Intelligent routing ...................... (ADR-0004, Accepted, refined)
5. Model-first orchestration + capability scoring  (ADR-0005, Accepted — pivotal)
6. Tier-aware, quota-preserving routing ..... (ADR-0006, Accepted — CURRENT)
```

Two later decisions layer on top of the evolution: **NVIDIA reintroduction** ([ADR-0007]) and the **DNA reframe** ([ADR-0010]).

---

## 3. Decision Records

### ADR-0001 — Start from static MODEL_POOLS
**Status:** Superseded by [ADR-0002]/[ADR-0005]. **Context:** earliest design used hardcoded static model pools. **Decision:** ship a fixed `MODEL_POOLS` mapping. **Consequence:** inflexible; couldn't adapt to availability/quota/capability. **Rejected as the final direction** (`PROJECT_ANALYSIS.md` L23). *Implemented by:* — (historical only).

### ADR-0002 — Multi-provider abstraction
**Status:** Accepted (refined by later ADRs). **Context:** a single provider is a single point of failure and limits model choice. **Decision:** abstract over multiple providers behind one interface; **provider-independent architecture** (L9). **Consequence:** providers become swappable; enables everything below. *Implemented by:* [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md).

### ADR-0003 — Provider manager
**Status:** Accepted. **Context:** multiple providers need lifecycle, registration, health. **Decision:** a provider manager that registers providers, tracks **health**, and exposes them uniformly. **Consequence:** health checks + availability become first-class (L39). *Implemented by:* [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md), [51_METRICS](./51_METRICS.md).

### ADR-0004 — Intelligent (dynamic) routing over static
**Status:** Accepted. **Context:** static routing can't react to health/quota/latency. **Decision:** **dynamic routing preferred over static** (L11). **Consequence:** routing becomes a runtime decision using live signals. *Implemented by:* [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md).

### ADR-0005 — Model-first orchestration with capability scoring (PIVOTAL)
**Status:** Accepted — **the central pivot.** **Context:** the earlier framing was **provider-first** (choose a provider, then a model). Reviewing an implementation plan surfaced that this is the wrong abstraction. **Decision:** shift to **model-first orchestration** — the system asks "what is the best *model* for this task?" and routes by **capability scoring**, not provider loyalty (L33, L57, L94–95). **Provider-first routing as the primary abstraction is rejected** (L21). **Consequence:** requires a capability taxonomy + scoring; providers become delivery channels for models. *Implemented by:* [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md), [46_CAPABILITY_TAXONOMY](./46_CAPABILITY_TAXONOMY.md), [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md).
> Note: `PROJECT_ANALYSIS.md` L95 records this "emerged after reviewing Claude's plan" — i.e., the pre-analysis documentation's provider-first direction was reviewed and **superseded** here.

### ADR-0006 — Tier-aware, quota-preserving routing (CURRENT)
**Status:** Accepted — **current state of the provider layer.** **Context:** cloud providers have tiers and quotas; naive routing exhausts quota and then degrades quality. **Decision:** routing is **tier-aware** and **quota-preserving**; **quality preservation across quota exhaustion is a core requirement** (L34, L43, L97). Adds **quota tracking + persistence** (L40, L84). **Consequence:** the router balances best-model-for-task against quota budgets and tiers. *Implemented by:* [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md), [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md).

### ADR-0007 — Reintroduce NVIDIA NIM as a primary provider
**Status:** **Rejected-then-Reversed → Accepted.** **Context:** NVIDIA NIM was earlier **rejected** (`PROJECT_ANALYSIS.md` L19, "Rejected Ideas") alongside Cerebras/HuggingFace. A **later** engineering decision **reintroduced NVIDIA NIM after adoption**. **Decision (latest, authoritative):** NVIDIA NIM **is a primary provider**, one of four, **not the flagship** and **not the "sovereign offline" path**. **This reverses the earlier rejection.** **Consequence:** the final primary provider set is **Gemini, Groq, OpenRouter, NVIDIA NIM**; NVIDIA is treated as a peer provider, not a differentiator. *Implemented by:* [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md), [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md).
> This ADR is the canonical illustration of the Chronological-Reading Rule (§0). The "Rejected Ideas" list captured the *earlier* state.

### ADR-0008 — Final provider architecture (4 primary + 1 fallback)
**Status:** Accepted (current). **Context:** the provider list was **repeatedly narrowed** over many conversations (L93). **Decision:** **Primary providers = Gemini, Groq, OpenRouter, NVIDIA NIM.** **Ollama = local/offline *fallback*, not a primary provider** (L8 lists Gemini/Groq/OpenRouter/Ollama; the later state per [ADR-0007] adds NVIDIA NIM as primary and demotes Ollama to fallback). **Consequence:** cloud is primary; local (Ollama) is the resilience/offline path — see [ADR-0010]. *Implemented by:* [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md), [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md), [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md).

### ADR-0009 — Smart failover / retry / timeout / cooldown (not simple static failover)
**Status:** Accepted. **Context:** simple static failover is insufficient for a multi-provider system with quotas/rate-limits. **Decision:** **automatic failover, retry, timeout, cooldown** (L10) with **smart failover + smart retry** (L37–38); **simple static failover is rejected** (L22). A provider that errors/rate-limits enters a **cooldown** before retry. **Consequence:** resilience is a first-class, tested behavior. *Implemented by:* [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) §failover, [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md).

### ADR-0010 — DNA reframe: cloud-primary, offline-fallback, light privacy
**Status:** Accepted (supersedes the pre-analysis "offline-first sovereign" framing). **Context:** the pre-analysis docs framed the product as **offline-first, sovereign, heavy-privacy**. The recovered DNA is **"offline fallback"** with cloud providers as primary, and it **rejects "large privacy/key-management sections"** and **"heavy keyring dependency"** (L25, L24, L69). **Decision:** the product is **cloud-primary with a local (Ollama) offline fallback**; key handling is **light** ("API keys outside source code", L13) — not a heavy OS-keychain vault; privacy sections are **slim**. The **Turkish-native, agentic, memory/audit** identity is retained. **Consequence:** reframe [00_PROJECT_VISION](./00_PROJECT_VISION.md) P1, [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md), [34_API_KEYS](./34_API_KEYS.md), [30_SECURITY](./30_SECURITY.md). *Implemented by:* those docs.

### ADR-0011 — Two orthogonal control dials (compute-depth + cost/quota)
**Status:** Accepted. **Context:** the pre-analysis docs had one compute-depth "effort" dial; the analysis proposes **Performance/Balanced/Economy** cost modes (L54). **Decision:** **two orthogonal dials** — (1) compute-depth effort (Hızlı/Dengeli/Derin/Maksimum) and (2) **cost/quota mode (Performance / Balanced / Economy)** that drives routing/quota aggressiveness. **Consequence:** users independently trade *thinking depth* and *cost/quota*. *Implemented by:* [17_EFFORT_MODES](./17_EFFORT_MODES.md).

### ADR-0012 — Provider-agnostic agents (agent/provider decoupling)
**Status:** Accepted. **Context:** agents must not be coupled to a specific provider/model. **Decision:** **agents remain provider-agnostic**; they request capabilities, the router picks the model (L15, L70). **Consequence:** switching providers/models requires **no agent changes**. *Implemented by:* [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md), [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md).

### ADR-0013 — 24-hour model cache
**Status:** Accepted (proposed). **Context:** enumerating provider models on every run is slow/wasteful. **Decision:** a **24-hour model cache** with a defined **refresh policy** (L96, L83). **Consequence:** fast startup + routing; requires cache invalidation/refresh rules. *Implemented by:* [49_MODEL_CACHE](./49_MODEL_CACHE.md).

### ADR-0014 — Engineering principles: SOLID, DI, single-provider responsibility, interface-driven
**Status:** Accepted. **Context:** to keep providers swappable and future providers cheap. **Decision:** apply **SOLID + Dependency Injection**; **each provider is a single responsibility**; **interface-driven design**; **future providers require minimal changes** (L14, L73–78). **Consequence:** adding a provider = implement one interface, register it — no core changes. *Implemented by:* [02_DESIGN_PRINCIPLES](./02_DESIGN_PRINCIPLES.md), [36_CODING_STANDARDS](./36_CODING_STANDARDS.md), [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md).

---

## 4. Rejected Ideas (with chronology)

From `PROJECT_ANALYSIS.md` §"Rejected Ideas" (L17–26). **Each is annotated with its current status** — because some were reversed:

| Idea | Status | Note |
|---|---|---|
| **Cerebras support** | Rejected | No confirmed reversal. See [43_NON_GOALS](./43_NON_GOALS.md). |
| **NVIDIA NIM support** | **REVERSED → Accepted** | Reintroduced as a primary provider ([ADR-0007]). **Not a current non-goal.** |
| **HuggingFace support** | Rejected | No confirmed reversal. |
| **Provider-first routing (primary abstraction)** | Rejected | Superseded by model-first ([ADR-0005]). |
| **Simple static failover as sufficient** | Rejected | Superseded by smart failover/cooldown ([ADR-0009]). |
| **Static MODEL_POOLS as final direction** | Rejected | Superseded by dynamic/model-first ([ADR-0004]/[ADR-0005]). |
| **Heavy keyring dependency** | Rejected | Light key handling instead ([ADR-0010]). |
| **Large privacy/key-management sections** | Rejected | Slim sections instead ([ADR-0010]). |
| **Hybrid mode as a separate architecture** | Rejected | Not a distinct architecture; routing already spans local+cloud. |

> **Maintenance rule:** never copy this table into another doc as "final non-goals." Only [43_NON_GOALS](./43_NON_GOALS.md) lists non-goals, and it **excludes** the reversed items (NVIDIA). If a rejected item is later reversed, add a new ADR and update this Status column.

---

## 5. Open / Undecided (recovered as gaps, not yet designed)

`PROJECT_ANALYSIS.md` §"Missing Documentation" lists concerns the conversations did **not** fully specify. These are **open design questions**, to be resolved in the named docs and marked `OPEN` there (not fabricated as recovered fact):

- Capability taxonomy **values** → [46_CAPABILITY_TAXONOMY](./46_CAPABILITY_TAXONOMY.md).
- Scoring **formulas** → [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md).
- Cache **refresh policy** specifics → [49_MODEL_CACHE](./49_MODEL_CACHE.md).
- Quota **persistence** mechanism → [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md).
- Benchmark **methodology** → [50_BENCHMARK_SPEEDTEST](./50_BENCHMARK_SPEEDTEST.md).
- Router **decision flow** + **failure state diagrams** → [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md).
- **Metrics definitions** → [51_METRICS](./51_METRICS.md).
- Chronology of the *other* rejected items (only NVIDIA's reversal is founder-confirmed) → confirm before treating as final.

---

## 5b. Coverage Reconciliation (`PROJECT_ANALYSIS.md` → docs)

Proof that every section of the recovered analysis is now reflected (chronology applied):

| `PROJECT_ANALYSIS.md` section | Reflected in |
|---|---|
| Final Accepted Decisions (L6–15) | [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md), [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md), [34_API_KEYS](./34_API_KEYS.md), ADR-0002/0005/0008/0012/0014 |
| Rejected Ideas (L17–26) | §4 table + [43_NON_GOALS](./43_NON_GOALS.md) §1b (NVIDIA reversed, ADR-0007) |
| Architecture Evolution (L28–34) | §2 + ADR-0001…0006 |
| Feature Evolution (L36–45) | [45](./45_ROUTING_ORCHESTRATION.md), [47](./47_SCORING_ALGORITHMS.md), [48](./48_QUOTA_TIER_MANAGEMENT.md), [51](./51_METRICS.md) |
| UI Evolution (L47–54) | [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md) §6.8, [50_BENCHMARK_SPEEDTEST](./50_BENCHMARK_SPEEDTEST.md), [17_EFFORT_MODES](./17_EFFORT_MODES.md) §4b |
| Philosophy (L56–60) | [00_PROJECT_VISION](./00_PROJECT_VISION.md) P1, ADR-0005/0010 |
| Project DNA (L62–70) | [00_PROJECT_VISION](./00_PROJECT_VISION.md), [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md), ADR-0010 |
| Engineering Principles (L72–78) | [02_DESIGN_PRINCIPLES](./02_DESIGN_PRINCIPLES.md) PR-19/20/21, [36_CODING_STANDARDS](./36_CODING_STANDARDS.md), ADR-0014 |
| Missing Documentation (L80–90) | new docs [45](./45_ROUTING_ORCHESTRATION.md)–[51](./51_METRICS.md) (with `OPEN` markers); config precedence + testing already in [33](./33_CONFIGURATION.md)/[35](./35_TESTING.md) |
| Conversation-only Details (L92–97) | ADR-0005 (Claude-plan pivot), ADR-0006 (quality-under-quota), ADR-0013 (24h cache), §2 (narrowing) |

## 6. Relationship With Other Subsystems

This log is the *why-history* behind the provider/LLM layer ([21](./21_PROVIDER_SYSTEM.md), [45](./45_ROUTING_ORCHESTRATION.md)–[51](./51_METRICS.md)) and the DNA reframe ([00](./00_PROJECT_VISION.md), [30](./30_SECURITY.md), [32](./32_OFFLINE_FIRST.md), [34](./34_API_KEYS.md), [17](./17_EFFORT_MODES.md)). Non-goals derive from §4 (minus reversals) into [43_NON_GOALS](./43_NON_GOALS.md). Registered in [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md).

## 7. Migration Considerations

New decisions append new ADRs; reversals mark the old ADR and add a new one (never edit history). If `PROJECT_ANALYSIS.md` is updated with more conversation history, re-apply the Chronological-Reading Rule (§0) and reconcile here first, then into the subsystem docs ([40_DOCUMENTATION_RULES](./40_DOCUMENTATION_RULES.md)).
