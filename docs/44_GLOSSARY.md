# 44 — Glossary (Sözlük)

> Part of the **turkish.code Engineering Bible**. Canonical terminology reference.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Rule:** These terms are **binding**. Use them verbatim in code identifiers, UI strings, docs, IPC method names, and commit messages. If a concept is not here, define it here before using it widely.
> **Related:** every document. This is the shared vocabulary.

---

## 1. Purpose

To eliminate ambiguity. A single canonical name per concept, in both Turkish and English, so that no two documents (or two developers, or two AI agents) invent competing words for the same thing. Terminology drift is the leading cause of architectural rot; this document exists to prevent it.

## 2. How To Read This

Each entry: **Canonical Term (Turkish) / English** — definition. *Code identifier* is the snake_case / PascalCase form used in source. *See:* points to the authoritative document.

Casing note: Turkish names appear in prose with correct Turkish orthography. In code identifiers we use ASCII transliteration (no diacritics) to avoid cross-platform filename and identifier hazards — e.g., `cini-mavi` not `çini-mavi`. This rule is defined once here and enforced in [36_CODING_STANDARDS](./36_CODING_STANDARDS.md).

---

## 3. The Three Tiers (Process Architecture)

- **Arayüz / Frontend** — The presentation tier: React 19 + TypeScript running inside the Tauri WebView. Contains **no business logic**. *Code:* `apps/desktop/src`. *See:* [03_UI_SYSTEM](./03_UI_SYSTEM.md).
- **Kabuk / Shell** — The trusted broker tier: the Rust/Tauri process. Owns OS access, process supervision, secrets, permission enforcement, and IPC routing. *Code:* `apps/desktop/src-tauri`. *See:* [07_DESKTOP_ARCHITECTURE](./07_DESKTOP_ARCHITECTURE.md), [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md).
- **Çekirdek / Core** — The AI brain tier: the Python 3.12+ sidecar process. Owns reasoning, agents, memory, RAG, embeddings, providers, tools, skills. *Code:* `core/turkish_code`. *See:* [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md).

## 4. Communication & Control

- **IPC** — Inter-process communication. Two links: the **Bridge** (Frontend↔Shell, Tauri commands/events) and the **Çekirdek Kanalı / Core Channel** (Shell↔Core, JSON-RPC 2.0 over length-prefixed stdio). *See:* [10_IPC](./10_IPC.md).
- **Bridge / Köprü** — The Frontend↔Shell IPC link (Tauri `invoke` + events).
- **Core Channel / Çekirdek Kanalı** — The Shell↔Core IPC link. No network port by default.
- **Envelope / Zarf** — The standard message wrapper on the Core Channel (id, method, params, meta). *See:* [10_IPC](./10_IPC.md).
- **Stream / Akış** — A sequence of incremental IPC notifications correlated to one request (e.g., token stream). *See:* [10_IPC](./10_IPC.md).

## 5. Intelligence Subsystems

- **Muhakeme / Reasoning Engine** — The orchestrator that runs the plan→act→observe→reflect loop, applies effort modes, and produces reasoning traces. *Code:* `core/turkish_code/muhakeme`. *See:* [15_REASONING_ENGINE](./15_REASONING_ENGINE.md).
- **Reasoning Trace / Muhakeme İzi** — The structured, inspectable record of a reasoning run (steps, tool calls, observations, reflections). Persisted to the Timeline.
- **Divan / Council** — Multi-persona deliberation mode: several model "experts" propose, critique, and a synthesizer reconciles. *Code:* `core/turkish_code/divan`. *See:* [16_COUNCIL_MODE](./16_COUNCIL_MODE.md).
- **Persona / Üye** — A single participant in a Divan session (a configured model + role prompt + stance).
- **Effort Mode / Çaba Modu** — A named compute/latency/quality tier (Hızlı, Dengeli, Derin, Maksimum) controlling token budgets, loop depth, retrieval depth, council size, reflection passes. *See:* [17_EFFORT_MODES](./17_EFFORT_MODES.md).
- **Agent / Ajan** — An autonomous unit with a role, instructions, tool grants, memory scope, and lifecycle. Agents can spawn sub-agents. *Code:* `core/turkish_code/ajan`. *See:* [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md).
- **Orchestrator Agent / Yönetici Ajan** — The top-level agent that decomposes goals and delegates to sub-agents.
- **Skill / Yetenek** — A modular capability package (instructions + optional assets/code) loaded via progressive disclosure when relevant. *Code:* `skills/`. *See:* [19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md), [SKILLS.md](./SKILLS.md).
- **Tool / Araç** — An executable capability with a typed schema, invoked by the agent, permission-gated by the Shell. *Code:* `core/turkish_code/araclar`. *See:* [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md).
- **Tool Call / Araç Çağrısı** — A single invocation of a tool with arguments, producing a result or error.

## 6. Knowledge Subsystems

- **Bellek / Memory** — The layered, durable memory system (working, semantic/long-term, profile, feedback). *Code:* `core/turkish_code/bellek`. *See:* [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md).
- **Working Memory / Çalışan Bellek** — Ephemeral, session-scoped context.
- **Semantic Memory / Anlamsal Bellek** — Durable long-term memory, vector-indexed.
- **Profile Memory / Profil Belleği** — Durable facts about the user.
- **Feedback Memory / Geri Bildirim Belleği** — Durable guidance the user gave about how the agent should behave.
- **Bilgi Grafı / Knowledge Graph** — Entities and typed relations extracted from code, docs, and conversation. *Code:* `core/turkish_code/graf`. *See:* [12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md).
- **Entity / Varlık** and **Relation / İlişki** — Nodes and edges in the Bilgi Grafı.
- **Getirim / Retrieval (RAG)** — The retrieval-augmented pipeline: chunk→embed→index→retrieve→rerank→assemble. *Code:* `core/turkish_code/getirim`. *See:* [13_RAG_SYSTEM](./13_RAG_SYSTEM.md).
- **Chunk / Parça** — A retrievable unit of text/code with metadata.
- **Embedding / Gömme** — A dense vector representation of a chunk or query. *See:* [14_EMBEDDINGS](./14_EMBEDDINGS.md).
- **Reranker / Yeniden Sıralayıcı** — A model that re-scores candidate chunks for a query. *See:* [14_EMBEDDINGS](./14_EMBEDDINGS.md).
- **Context Assembly / Bağlam Kurulumu** — Building the final prompt context from retrieved chunks, memory, and instructions under a token budget.

## 7. Providers, Routing & Extensibility

- **Provider / Sağlayıcı** — A **single-responsibility** adapter to a model backend behind a uniform, **provider-independent** interface. Primary: **Gemini, Groq, OpenRouter, NVIDIA NIM**; **Ollama** = local/offline fallback. *Code:* `core/turkish_code/saglayicilar`. *See:* [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md), [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md).
- **Model-First / Model-Öncelikli** — The core philosophy: choose the **best model for the task**, then whichever provider delivers it — *not* provider-first. *See:* [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md), [52_ADR_LOG](./52_ADR_LOG.md) ADR-0005.
- **Router / Yönlendirici** — Selects the model per request (dynamic, capability + score + quota + health). *See:* [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md).
- **Capability (model) / Model Yeteneği** — A model's abilities in the taxonomy (reasoning, code, Turkish quality, tool-use, context, latency, cost). *See:* [46_CAPABILITY_TAXONOMY](./46_CAPABILITY_TAXONOMY.md). (Distinct from a permission **Capability / Yetki**, §8.)
- **Score / Puan** — The number ranking a candidate model (model score × provider score, mode-weighted). *See:* [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md).
- **Quota / Kota · Tier / Kademe · Cooldown** — Provider usage limits, plan levels, and the "skip while rate-limited" state; drive **quota-preserving routing**. *See:* [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md).
- **Cost/Quota Mode / Maliyet Modu** — The second effort dial: **Performance / Balanced / Economy**. *See:* [17_EFFORT_MODES](./17_EFFORT_MODES.md) §4b.
- **Model Cache / Model Önbelleği** — 24-hour cache of provider model lists. *See:* [49_MODEL_CACHE](./49_MODEL_CACHE.md).
- **NIM** — NVIDIA Inference Microservice (cloud or self-hosted); **one primary provider among four**, not flagship. *See:* [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md), [52_ADR_LOG](./52_ADR_LOG.md) ADR-0007.
- **Ollama** — Local model runtime used as the **offline fallback** (not a primary provider). *See:* [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md).
- **Plugin / Eklenti** — A distributable extension bundling any of: skills, tools, providers, agents, UI panels. Sandboxed, capability-gated. *Code:* `plugins/`. *See:* [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md).

## 8. Safety, State & History

- **Permission / İzin** — A capability grant governing a potentially sensitive action. Enforced in the Kabuk. *See:* [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md).
- **Permission Mode / İzin Modu** — A session policy: `plan` (read-only), `ask` (prompt per sensitive action), `auto` (pre-granted within scope). *See:* [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md).
- **Capability / Yetki** — A named, grantable right (e.g., `fs.write`, `net.egress`, `shell.exec`).
- **Çalışma Alanı / Workspace** — A project root the agent operates on, with its own DB, config, index, and memory scope. *See:* [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md).
- **Zaman Çizelgesi / Timeline** — The append-only, ordered event log of everything perceived and done. *See:* [26_TIMELINE](./26_TIMELINE.md).
- **Event / Olay** — A single immutable record in the Timeline.
- **Anlık Görüntü / Snapshot** — A content-addressed point-in-time capture of workspace file state enabling perfect rollback. *See:* [27_SNAPSHOTS](./27_SNAPSHOTS.md).
- **Content-Addressed / İçerik Adresli** — Storage keyed by the BLAKE3 hash of content. *See:* [29_STORAGE](./29_STORAGE.md).
- **Session / Oturum** — One continuous unit of work with the agent (a conversation + its reasoning + its edits). Recoverable after crash.
- **Checkpoint / Denetim Noktası** — A durably-persisted, resumable state marker within a session. *See:* [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md).

## 9. Design & Presentation

- **Türk Tasarım Dili / Turkish Design Language (TTD)** — The bespoke design system: tokens, motifs, palette, typography, motion. *See:* [04_TURKISH_DESIGN_LANGUAGE](./04_TURKISH_DESIGN_LANGUAGE.md).
- **Design Token / Tasarım Belirteci** — A named design value (color, space, radius, motion). *See:* [03_UI_SYSTEM](./03_UI_SYSTEM.md).
- **Motif / Motif** — An abstracted Anatolian/Seljuk geometric pattern used as texture/accent.
- **Component / Bileşen** — A reusable UI element in the component library. *See:* [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md).

## 10. Storage & Data

- **App DB / Uygulama VT** — The global SQLite database (settings, providers, plugin registry). *See:* [29_STORAGE](./29_STORAGE.md).
- **Workspace DB / Çalışma Alanı VT** — Per-workspace SQLite database (index, memory, timeline).
- **Blob Store / Blob Deposu** — Content-addressed filesystem store for snapshots and large artifacts.
- **Event Journal / Olay Günlüğü** — The append-only write-ahead log backing the Timeline and crash recovery.
- **Vector Store / Vektör Deposu** — sqlite-vec-backed table(s) holding embeddings.

## 11. Cross-Cutting

- **Offline Fallback / Çevrimdışı Yedek** — Resilience: when cloud providers are unreachable, the router degrades to a local **Ollama** model so core capability keeps working (reduced quality). The product is **cloud-primary**, not "offline-first." *See:* [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md), [52_ADR_LOG](./52_ADR_LOG.md) ADR-0010.
- **Egress / Dışa Aktarım** — Any data leaving the device. Always consent-gated and logged. *See:* [30_SECURITY](./30_SECURITY.md).
- **Consent / Rıza** — An explicit, revocable, per-category user authorization (e.g., allow cloud provider). *See:* [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md), [34_API_KEYS](./34_API_KEYS.md).
- **Effort Budget / Çaba Bütçesi** — The concrete numeric limits derived from the active Effort Mode.
- **Degradation / Kademeli Düşüş** — Reducing ambition (smaller model, no rerank, etc.) rather than failing. *See:* [31_PERFORMANCE](./31_PERFORMANCE.md), [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md).

## 12. Reserved Words / Forbidden Aliases

To prevent drift, these synonyms are **forbidden**; use the canonical term instead:

| Do NOT use | Use instead |
|---|---|
| "backend", "server", "daemon" (for the Python tier) | **Çekirdek / Core** |
| "wrapper", "shell script" (for the Rust tier) | **Kabuk / Shell** |
| "UI thread", "webview code" loosely | **Arayüz / Frontend** |
| "vector db as a service" | **Vector Store** (embedded) |
| "history", "log" (for the event record) | **Timeline** / **Event Journal** (distinct: see [26_TIMELINE](./26_TIMELINE.md)) |
| "checkpoint" for file state | **Snapshot** (Snapshot = files; Checkpoint = session state) |
| "plugin" for internal skills | **Skill** (internal) vs **Plugin** (distributable) |
| "committee", "jury", "ensemble" | **Divan / Council** |

## 13. Abbreviations

TTD (Türk Tasarım Dili) · KG (Bilgi Grafı / Knowledge Graph) · RAG (Getirim) · IPC · VT (Veritabanı / Database) · NIM (NVIDIA Inference Microservice) · UDS (Unix Domain Socket) · WAL (Write-Ahead Log) · CAS (Content-Addressed Storage).

## 14. Maintenance

New terms are added here **in the same change** that introduces them. A term is never renamed silently; a rename is a documented migration (see [40_DOCUMENTATION_RULES](./40_DOCUMENTATION_RULES.md)). The [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md) links here as the terminology authority.
