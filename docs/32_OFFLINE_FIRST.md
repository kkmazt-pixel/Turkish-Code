# 32 — Offline Fallback (Çevrimdışı Yedek)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 2.0 · **Last updated:** 2026-07-12
> **Owner:** cross-cutting
> **Changed in v2.0** (per [52_ADR_LOG](./52_ADR_LOG.md) ADR-0008/0010): the product is **cloud-primary**; offline is a **fallback** (via local **Ollama**), **not** "offline-first." Cloud providers are the normal path; the local path is *resilience*, not the defining constraint.
> **Related:** [00_PROJECT_VISION](./00_PROJECT_VISION.md) (P1) · [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) · [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md) · [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) · [52_ADR_LOG](./52_ADR_LOG.md)

---

## 1. Purpose

Defines the **offline fallback** — how turkish.code stays useful when the network or all cloud providers are unavailable, by falling back to a **local Ollama model**. This is a **resilience** feature layered under a **cloud-primary** architecture ([52](./52_ADR_LOG.md) ADR-0008/0010), *not* the sovereign "offline-first" posture of v1.0. The primary providers (Gemini/Groq/OpenRouter/NVIDIA NIM) are the normal path ([22](./22_PROVIDER_INTEGRATIONS.md)); when they can't be reached, the router degrades to Ollama so the user is never fully blocked.

## 2. Scope

The offline-fallback guarantee and its boundaries, what works with Ollama-only, the router's fallback behavior, network-state handling, and verification. Out of scope: routing mechanics ([45](./45_ROUTING_ORCHESTRATION.md)), provider internals ([21](./21_PROVIDER_SYSTEM.md)/[22](./22_PROVIDER_INTEGRATIONS.md)), keys ([34](./34_API_KEYS.md)).

## 3. The Offline-Fallback Guarantee

**When cloud providers are unreachable (offline or all exhausted/down), the user can still:** open a workspace; index it (local embeddings); ask questions in Turkish; reason with the agent; edit files (snapshot-backed); run commands/tests; use memory, knowledge graph, RAG, effort modes, agents, skills, timeline, snapshots, and recovery — using a **local Ollama model**. Quality may be lower than a strong cloud model (bounded by the user's local hardware), but the product **keeps working** rather than hard-failing (PR-7). Council may degrade to single-model multi-stance ([16](./16_COUNCIL_MODE.md)).

The router ([45](./45_ROUTING_ORCHESTRATION.md) §6) engages the Ollama fallback automatically as the last resort; the user can also *prefer* local explicitly (cost/quota dial or a policy pin, [17](./17_EFFORT_MODES.md)/[21](./21_PROVIDER_SYSTEM.md)).

## 4. Design Rule (PR-7 Degradation)

Cloud-primary, **local-fallback**: the normal path routes to the best cloud model ([45](./45_ROUTING_ORCHESTRATION.md)); when that's impossible, **degrade to Ollama** rather than fail (PR-7). This is a *degradation ladder*, not an "offline-first, local-only path first" rule. (This supersedes v1.0's PR-6 "local path first" framing for the model layer; other bundled assets — fonts/icons — remain local for UX reasons, [04](./04_TURKISH_DESIGN_LANGUAGE.md).)

## 5. Per-Subsystem Local Paths (Map)

| Capability | Local (offline) path |
|---|---|
| Chat/reasoning ([15](./15_REASONING_ENGINE.md)) | local LLM via NIM/llama.cpp/Ollama ([21](./21_PROVIDER_SYSTEM.md)/[22](./22_PROVIDER_INTEGRATIONS.md)) |
| Embeddings ([14](./14_EMBEDDINGS.md)) | local embedder (NeMo local / ONNX / GGUF) |
| Rerank ([13](./13_RAG_SYSTEM.md)) | local reranker, or fusion-only if none (PR-7) |
| Retrieval/index ([13](./13_RAG_SYSTEM.md)) | sqlite-vec + FTS5, fully local ([29](./29_STORAGE.md)) |
| Knowledge graph ([12](./12_KNOWLEDGE_GRAPH.md)) | tree-sitter parsers bundled, local extraction |
| Memory ([11](./11_MEMORY_SYSTEM.md)) | local DB + local embeddings |
| Council ([16](./16_COUNCIL_MODE.md)) | single local model, multi-stance personas |
| Tools/permissions/snapshots/timeline/recovery/storage | inherently local (Kabuk/Çekirdek/SQLite) |
| Design/UI/fonts/icons/motifs | bundled, no CDN ([03](./03_UI_SYSTEM.md)/[04](./04_TURKISH_DESIGN_LANGUAGE.md)) |

There is **no core row without a local path**. If a proposed feature has none, it isn't core (or it isn't built) — [43_NON_GOALS](./43_NON_GOALS.md).

## 6. The Only Sanctioned Egress: Acquisition (Consent-Gated)

- The app ships small; **models and some assets are fetched on first use** — this is the one common egress, and it is **consent-gated** ([24](./24_PERMISSION_SYSTEM.md) §9, PR-16), checksum-verified ([30](./30_SECURITY.md)/[22](./22_PROVIDER_INTEGRATIONS.md)), and resumable.
- **Air-gapped path:** an offline installer variant pre-bundles a verified default local model, and models can be sideloaded from local files — so a machine that *never* touches the network can be fully set up ([07](./07_DESKTOP_ARCHITECTURE.md) §6).
- After acquisition, everything runs offline forever. Acquisition is a one-time, visible, optional step — not an ongoing dependency.

## 7. Online ↔ Offline Transitions

- **Network state is observed** ([07](./07_DESKTOP_ARCHITECTURE.md) §9); the provider registry updates availability ([21](./21_PROVIDER_SYSTEM.md) §6) and the UI shows the current posture ([06](./06_COMPONENT_LIBRARY.md) §6.8).
- **Going offline mid-session:** the agent seamlessly routes to local providers ([21](./21_PROVIDER_SYSTEM.md) §9); if a cloud call was in flight, it fails over/degrades — **work never blocks on the network** (PR-6). The user is notified because the privacy/quality posture changed.
- **Coming online:** nothing changes automatically; cloud remains **off until consented** (no silent switch, PR-16, [30](./30_SECURITY.md)).

## 8. Default Posture

- **Default = fully local, cloud disabled, no egress, telemetry off** ([24](./24_PERMISSION_SYSTEM.md)/[30](./30_SECURITY.md)/[33](./33_CONFIGURATION.md)). The product is designed to be *complete* in this state; enabling cloud is a deliberate upgrade, not a fix for a hobbled default.

## 9. Configuration

- Model cache location, default local models per role ([21](./21_PROVIDER_SYSTEM.md)/[22](./22_PROVIDER_INTEGRATIONS.md)), acquisition consent, air-gapped mode, and "never go online" lock are configurable ([33](./33_CONFIGURATION.md)). Enterprises can hard-lock offline.

## 10. Dependencies

- Local model runtimes + bundled parsers/fonts/assets, [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md)/[22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md) (local providers), [29_STORAGE](./29_STORAGE.md) (local persistence), [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md)/[30_SECURITY](./30_SECURITY.md) (egress consent), [07_DESKTOP_ARCHITECTURE](./07_DESKTOP_ARCHITECTURE.md) (packaging/network state).

## 11. Edge Cases

- **No model installed yet + offline:** onboarding blocks gracefully with instructions to sideload a local model (air-gapped path); never a dead end that demands the internet.
- **Partial cache (some models present):** available capabilities work; missing-model capabilities degrade or prompt for (consented) acquisition.
- **Cloud configured but offline:** cloud unavailable → local path; clearly indicated.
- **Weak hardware offline:** small local models + capped effort ([17](./17_EFFORT_MODES.md)/[31](./31_PERFORMANCE.md)) — slower, still functional.
- **Bundled asset accidentally references a CDN:** forbidden (CSP + tests catch it, [03](./03_UI_SYSTEM.md)/[04](./04_TURKISH_DESIGN_LANGUAGE.md)).
- **Update available but offline/no consent:** app keeps working on the installed version ([07](./07_DESKTOP_ARCHITECTURE.md)).

## 12. Failure Recovery

- Offline is a first-class normal state, not a failure. Losing connectivity degrades cloud-only extras gracefully ([21](./21_PROVIDER_SYSTEM.md) §9) and never loses work ([28](./28_CRASH_RECOVERY.md)). Interrupted acquisition resumes/verifies ([22](./22_PROVIDER_INTEGRATIONS.md)).

## 13. Security

- Offline-first *is* a privacy control: no network = no exfiltration surface ([30](./30_SECURITY.md)). The only egress (acquisition) is consented + verified. Default-offline minimizes attack surface (no ports, no calls) — aligns with [30](./30_SECURITY.md) §4.

## 14. Performance

- Local-first is also faster (no round-trips) for many operations; GPU local inference ([22](./22_PROVIDER_INTEGRATIONS.md)) rivals cloud on capable hardware. Offline removes network variance from latency ([31](./31_PERFORMANCE.md)).

## 15. Testing Strategy

- **The offline gate (marquee):** a CI suite runs the **entire core flow with the network disabled** (open→index→ask→edit→test→recover) using only local models — it must pass. Any core feature that fails offline is a release blocker.
- **No-CDN test:** assert zero runtime external requests (CSP + network monitor).
- **Air-gapped install test:** offline installer + sideloaded model → full function.
- **Transition tests:** go offline mid-session → seamless local failover, no lost work; come online → no silent cloud switch. See [35_TESTING](./35_TESTING.md).

## 16. Future Extensions

- Curated offline model bundles per hardware tier; LAN model sharing (a trusted local GPU box, still consent-gated, [01](./01_ARCHITECTURE.md) §19); delta model updates; better small-model quality for Tier C.

## 17. Examples

- Kerem (air-gapped, [00](./00_PROJECT_VISION.md) persona) installs the offline variant, sideloads a local model, and runs the full agent on a classified codebase with the machine's network physically disconnected — every core feature works.

## 18. Anti-Patterns

- A core feature that silently requires the network ("just to be faster").
- "Cloud first, offline fallback" control flow (must be the reverse).
- Runtime-fetched fonts/assets/telemetry.
- Silent online switch when connectivity returns.
- Treating offline as an error state to recover from.

## 19. Things That Must Never Happen

1. A **core** capability is unavailable solely because the machine is offline.
2. Any egress occurs without explicit consent (even "harmless" checks).
3. A runtime dependency (font/asset/model) is fetched without consent.
4. Connectivity returning silently enables cloud/egress.
5. The default install is functionally crippled without the network.

## 20. Relationship With Other Subsystems

Realized by local paths in [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md)/[22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md)/[14_EMBEDDINGS](./14_EMBEDDINGS.md)/[13_RAG_SYSTEM](./13_RAG_SYSTEM.md)/[12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md)/[11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md)/[16_COUNCIL_MODE](./16_COUNCIL_MODE.md); egress governed by [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md)/[30_SECURITY](./30_SECURITY.md); acquisition/packaging via [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md)/[07_DESKTOP_ARCHITECTURE](./07_DESKTOP_ARCHITECTURE.md); the direct expression of Pillar P1 ([00](./00_PROJECT_VISION.md)) and PR-6 ([02](./02_DESIGN_PRINCIPLES.md)).

## 21. Migration Considerations

- The offline guarantee is effectively immutable (P1); a change that weakened it would require a vision revision ([00](./00_PROJECT_VISION.md)) and is presumed forbidden. Default local models evolve ([21](./21_PROVIDER_SYSTEM.md)/[14](./14_EMBEDDINGS.md), possibly re-embed); the air-gapped path is preserved across versions.
