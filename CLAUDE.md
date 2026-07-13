# CLAUDE.md — Entry Point for AI Agents & Developers

This is **turkish.code** — a **Turkish-native, agentic AI software-engineering desktop app**
whose intelligence is a **multi-provider, model-first LLM orchestration core**
(**Gemini · Groq · OpenRouter · NVIDIA NIM**) with a **local Ollama offline fallback**.
The complete engineering specification (the "Engineering Bible") lives in [`docs/`](./docs/).

## Start Here

1. **[docs/ARCHITECTURE_INDEX.md](./docs/ARCHITECTURE_INDEX.md)** — the master map: catalog,
   diagrams, implementation order, and the **AI/Developer Onboarding Guide**.
2. **[docs/52_ADR_LOG.md](./docs/52_ADR_LOG.md)** — the decision history and the **chronological-reading
   rule**. `PROJECT_ANALYSIS.md` is a *timeline*: **always follow the latest decision** (e.g., NVIDIA NIM
   was rejected **then reintroduced** — it is a primary provider, not rejected).
3. **[docs/AGENTS.md](./docs/AGENTS.md)** — the operating contract for AI agents working in this repo.

## Core DNA (authoritative — v2.0)

- **Cloud-primary, model-first**: route to the **best model for the task** across four providers;
  **Ollama** is the **offline fallback** (not "offline-first"). See
  [docs/21_PROVIDER_SYSTEM.md](./docs/21_PROVIDER_SYSTEM.md), [docs/45_ROUTING_ORCHESTRATION.md](./docs/45_ROUTING_ORCHESTRATION.md).
- **Resilient routing**: capability + tier + **quota-preserving** (quality preserved under quota
  exhaustion) + smart failover/retry/timeout/cooldown; **24h model cache**; provider/model scoring.
- **Two dials**: compute-depth effort (Hızlı/Dengeli/Derin/Maksimum) + cost/quota (Performance/Balanced/Economy).
- **Provider-agnostic agents**; **SOLID + DI**; adding a provider = implement one interface, no core changes.
- **Light key handling** (keys out of source code, never logged) — **not** a heavy keychain vault.
- **Kept**: Turkish-native identity, agentic reasoning, memory/audit, Council/KG/RAG/Timeline/Snapshots, Tauri 3-tier.

## Non-Negotiables

- **Phase 1 is documentation only.** Do not implement code until authorized
  ([docs/42_ROADMAP.md](./docs/42_ROADMAP.md), [docs/41_IMPLEMENTATION_RULES.md](./docs/41_IMPLEMENTATION_RULES.md)).
- Every side effect is permission-gated + snapshotted + audited ([docs/24_PERMISSION_SYSTEM.md](./docs/24_PERMISSION_SYSTEM.md),
  [docs/27_SNAPSHOTS.md](./docs/27_SNAPSHOTS.md)); nothing is unbounded.
- Use canonical terminology ([docs/44_GLOSSARY.md](./docs/44_GLOSSARY.md)); keep docs in sync with code
  ([docs/40_DOCUMENTATION_RULES.md](./docs/40_DOCUMENTATION_RULES.md)).
