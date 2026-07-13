# 01 — System Architecture (Mimari)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Related:** [00_PROJECT_VISION](./00_PROJECT_VISION.md) · [07_DESKTOP_ARCHITECTURE](./07_DESKTOP_ARCHITECTURE.md) · [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) · [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md) · [10_IPC](./10_IPC.md) · [29_STORAGE](./29_STORAGE.md) · [44_GLOSSARY](./44_GLOSSARY.md)

---

## 1. Purpose

This document defines the **top-level technical architecture** of turkish.code: the process model, the tiers and their responsibilities, the trust boundaries, the data planes, the control flow of a request, and the global invariants. It is the map every other document plugs into. Subsystem documents describe the *inside* of a box; this document describes the *boxes and the wires between them*.

## 2. Scope

In scope: process/tier decomposition, trust boundaries, transport choices, the canonical end-to-end request lifecycle, global state ownership, cross-tier contracts, threading/concurrency model, and system-wide invariants. Out of scope: the internals of any single subsystem (see its numbered doc) and the rationale-level product intent (see [00_PROJECT_VISION](./00_PROJECT_VISION.md)).

## 3. Goals

1. Enforce the pillars from [00_PROJECT_VISION](./00_PROJECT_VISION.md) *structurally*, not by convention. Privacy and offline-first must be properties of the architecture, not promises.
2. A hard **trust boundary** between untrusted presentation (Arayüz) and privileged capability (Kabuk), with the AI brain (Çekirdek) sandboxed behind the broker.
3. A single, well-defined path for every side effect (file write, shell exec, network egress) so it can be permission-gated and logged in exactly one place.
4. Independent evolvability: swap the model brain, the UI framework, or the storage engine with contained blast radius.
5. Legibility to AI agents operating the system.

### Non-Goals
- Not a microservices/network architecture. It is a **local multi-process desktop app**. No always-on servers, no cloud control plane. (See [43_NON_GOALS](./43_NON_GOALS.md).)

## 4. The Three-Tier Process Model

turkish.code runs as **three cooperating processes** on the user's machine. This is the single most important architectural fact; internalize it.

```
┌───────────────────────────────────────────────────────────────────────┐
│  USER'S MACHINE (offline-capable)                                       │
│                                                                         │
│   ┌─────────────────────┐        ┌──────────────────────────────────┐  │
│   │  ARAYÜZ (Frontend)  │  Bridge │  KABUK (Shell) — Rust / Tauri    │  │
│   │  React 19 + TS      │◄───────►│  • Window & OS integration       │  │
│   │  in Tauri WebView   │  invoke │  • Process supervisor            │  │
│   │  Presentation only  │  events │  • PERMISSION ENFORCEMENT (choke │  │
│   └─────────────────────┘        │    point for all side effects)   │  │
│        (untrusted zone)          │  • Secret vault (OS keychain)    │  │
│                                  │  • IPC router                     │  │
│                                  └───────────────┬──────────────────┘  │
│                                                  │ Core Channel         │
│                                                  │ (JSON-RPC 2.0 over    │
│                                                  │  length-prefixed      │
│                                                  │  stdio; no TCP port)  │
│                                                  ▼                      │
│                                  ┌──────────────────────────────────┐  │
│                                  │  ÇEKİRDEK (Core) — Python 3.12+  │  │
│                                  │  The AI brain (sidecar):         │  │
│                                  │  Muhakeme · Divan · Ajanlar ·    │  │
│                                  │  Bellek · Bilgi Grafı · Getirim ·│  │
│                                  │  Gömme · Araçlar · Yetenekler ·  │  │
│                                  │  Sağlayıcılar                    │  │
│                                  └───────┬──────────────┬───────────┘  │
│                                          │              │              │
│                              ┌───────────▼──┐   ┌───────▼───────────┐  │
│                              │  STORAGE     │   │  LOCAL MODELS      │  │
│                              │  SQLite+vec  │   │  NIM / llama.cpp / │  │
│                              │  Blob (CAS)  │   │  Ollama (via       │  │
│                              │  Event Journ.│   │  Sağlayıcılar)     │  │
│                              └──────────────┘   └───────────────────┘  │
│                                                                         │
│   Network egress ONLY from Çekirdek, ONLY via Kabuk-granted consent ────┼──▶ (optional cloud)
└───────────────────────────────────────────────────────────────────────┘
```

### 4.1 Arayüz (Frontend) — the untrusted presentation tier
- Renders UI, handles interaction and animation, streams reasoning/results to the screen.
- **Holds no secrets, has no direct OS access, contains no business logic.** It is treated as an untrusted zone (it renders model output and could in principle be influenced by prompt-injected content). Everything it wants to *do* goes through the Bridge to the Kabuk.
- Details: [03_UI_SYSTEM](./03_UI_SYSTEM.md), [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md).

### 4.2 Kabuk (Shell) — the trusted broker tier
- The only tier with ambient OS authority. It is the **single choke point** through which every side effect must pass: file reads/writes, shell execution, network egress, secret access.
- Owns: window/OS integration, the Çekirdek process lifecycle (spawn/health/restart), the secret vault (OS keychain), the permission engine, and IPC routing between the Bridge and the Core Channel.
- Because it is small, statically-typed Rust with a narrow surface, it is the tier we most trust. Details: [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md), [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md).

### 4.3 Çekirdek (Core) — the AI brain tier
- All intelligence lives here: reasoning loop, agents, council, memory, knowledge graph, RAG, embeddings, tool implementations, provider adapters, skills.
- Runs as a **Tauri-managed sidecar** child process. It is *sandboxed*: it does not get raw OS capability; when it needs a side effect it requests it over the Core Channel and the Kabuk enforces permissions. (The Core *can* touch storage and spawn model runtimes it owns; the sensitive, user-visible side effects — writing the user's files, running arbitrary shell, egress — are brokered. See [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) §"Enforcement locus".)
- Details: [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md).

### 4.4 Why three processes (rationale)
- **Security:** a compromised or misbehaving WebView cannot directly touch the filesystem or network; a prompt-injected model cannot exfiltrate because egress is brokered. Trust decreases outward (Kabuk > Çekirdek > Arayüz).
- **Language fit:** Rust for a small safe broker; Python for the AI ecosystem (models, embeddings, ML libs); TS/React for UI. Each tier uses the best tool.
- **Isolation of failure:** the Core can crash and be restarted without killing the window; the WebView can reload without losing Core state. See [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md).
- **Resource control:** the heavy Python/model process is separately supervisable (memory limits, restart, GPU affinity).

Alternatives considered and rejected: (a) *single Electron+Node process* — rejected: no privilege separation, heavier, weaker Turkish/native feel. (b) *Python embedded in Rust via PyO3* — rejected: couples lifecycles, a Python segfault takes down the broker, harder to sandbox and restart. (c) *Frontend talks to Python directly over localhost HTTP* — rejected: opens a network port (attack surface + violates the no-port offline posture) and bypasses the Kabuk choke point. The sidecar-over-stdio model keeps the broker in the middle of every path.

## 5. Trust Boundaries

Two hard boundaries, each crossed only by a defined contract:

1. **Arayüz ⇄ Kabuk** (the Bridge). Crossing requires a Tauri command allowlisted in the Kabuk. The Arayüz can *request*; the Kabuk *decides*. No capability leaks across implicitly. See [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) §capabilities.
2. **Kabuk ⇄ Çekirdek** (the Core Channel). Crossing is JSON-RPC over stdio owned solely by the Kabuk. The Çekirdek cannot reach the Arayüz except *through* the Kabuk, and cannot perform brokered side effects except by asking the Kabuk. See [10_IPC](./10_IPC.md).

The storage layer and local model runtimes sit *inside* the Çekirdek's trust zone but are still subject to the pillar invariants (e.g., no plaintext secrets in SQLite — secrets live in the Kabuk's keychain vault). See [29_STORAGE](./29_STORAGE.md), [30_SECURITY](./30_SECURITY.md).

## 6. Data Planes

We distinguish three planes that must not be conflated:

- **Control plane** — request/response commands (start session, run tool, query memory). Low volume, latency-sensitive, JSON-RPC over the Core Channel and Tauri commands over the Bridge.
- **Stream plane** — high-frequency incremental events (token deltas, reasoning steps, log lines, progress). Modeled as correlated JSON-RPC notifications on the Core Channel, re-emitted to the Arayüz as Tauri events. See [10_IPC](./10_IPC.md) §streaming.
- **Bulk plane** — large binary payloads (file contents, embeddings, snapshot blobs). Kept *out* of the JSON control messages; transferred via the Blob Store references or an optional Unix-domain-socket/named-pipe channel to avoid bloating and blocking the control plane. See [10_IPC](./10_IPC.md) §bulk, [29_STORAGE](./29_STORAGE.md).

## 7. Global State Ownership

State has exactly one owner tier. Duplication is cache, and caches are explicitly labeled as such.

| State | Owner | Notes |
|---|---|---|
| UI/view state (open panels, scroll, theme toggle) | Arayüz | Ephemeral; may persist trivial prefs via Kabuk. |
| Window/OS state, secrets, permission grants | Kabuk | Secrets in OS keychain; grants in App DB (non-secret). |
| Sessions, reasoning, memory, KG, index, timeline | Çekirdek + Storage | Source of truth for all AI state. |
| Configuration | Files + App/Workspace DB | See [33_CONFIGURATION](./33_CONFIGURATION.md). |
| Model weights / runtimes | Çekirdek (filesystem) | See [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md). |

**Invariant:** the Arayüz never holds authoritative state. On reload it rehydrates from the Kabuk/Çekirdek. This makes WebView reloads and crashes non-destructive.

## 8. Canonical Request Lifecycle (End-to-End)

The single most important control-flow to understand. A user asks the agent to do something:

```
1. USER types a message / hits Run in Arayüz.
2. Arayüz → Bridge: invoke("session.send", {sessionId, text, effortMode}).
3. Kabuk validates the command against capabilities, attaches the session's
   permission context, and forwards over Core Channel:
     → JSON-RPC request "session.send" to Çekirdek.
4. Çekirdek (Muhakeme) begins a reasoning run:
     a. Assemble context: pull Working/Semantic memory (Bellek), retrieve
        relevant chunks (Getirim), graph facts (Bilgi Grafı), skills (Yetenekler).
     b. Enter plan→act→observe→reflect loop under the Effort Budget.
     c. Emits Stream notifications (reasoning steps, token deltas) continuously →
        Kabuk re-emits as Tauri events → Arayüz renders live.
5. When the model decides to use a Tool (Araç):
     a. Çekirdek → Core Channel request "tool.invoke" {name, args}.
     b. Kabuk consults the PERMISSION ENGINE:
        - read-only & in-scope → allowed.
        - sensitive (fs.write, shell.exec, net.egress) → per Permission Mode:
          plan → denied; ask → Kabuk asks Arayüz to prompt the user; auto → allowed
          if pre-granted.
     c. On allow, the SIDE EFFECT executes (in Kabuk for brokered ops, or in
        Çekirdek for its own ops), a SNAPSHOT is taken before file mutations,
        and an EVENT is appended to the Timeline.
     d. Result returns to Çekirdek; the model observes it and continues.
6. On completion, Çekirdek returns the final result over the Core Channel.
7. Kabuk relays to Arayüz; the reasoning trace, edits, and snapshots are all
   persisted and inspectable.
```

Every arrow that produces a side effect passes through the Kabuk permission engine (step 5b) — that is the structural guarantee behind P5. Every file mutation is preceded by a snapshot (step 5c) — the structural guarantee behind P4. See [15_REASONING_ENGINE](./15_REASONING_ENGINE.md), [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md), [26_TIMELINE](./26_TIMELINE.md), [27_SNAPSHOTS](./27_SNAPSHOTS.md).

## 9. Lifecycle of the System (Boot → Shutdown)

```
BOOT
 1. OS launches Kabuk (Tauri). Kabuk reads app config, opens App DB.
 2. Kabuk spawns Çekirdek sidecar with a per-session capability token via env,
    stdio pipes wired for the Core Channel.
 3. Çekirdek performs handshake: reports version, capabilities, available
    providers/models, and readiness. Kabuk records health.
 4. Kabuk creates the WebView, loads the Arayüz bundle.
 5. Arayüz calls "app.bootstrap" → gets locale, theme, last workspace, provider
    status. Renders. If a crashed session is detected, offers recovery
    (see [28_CRASH_RECOVERY]).
RUN
 6. Normal operation per §8. Kabuk continuously supervises Çekirdek health
    (heartbeat over Core Channel). On Çekirdek crash → restart + recover.
SHUTDOWN
 7. Arayüz/OS signals quit. Kabuk sends "app.shutdown" to Çekirdek (flush
    journals, close DBs, checkpoint sessions), waits with timeout, then
    terminates the sidecar, closes App DB, exits.
```

State machine for the Çekirdek process (owned by the Kabuk supervisor):

```
        spawn                handshake ok
 [Stopped] ─────▶ [Starting] ───────────▶ [Ready]
    ▲                 │ handshake fail        │ crash / no heartbeat
    │                 ▼                        ▼
    │            [Failed] ◀───── restart ─── [Recovering] ──ok──▶ [Ready]
    └──── stop ────────┘  (backoff, max N)
```

See [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) for the supervisor and [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md) for recovery.

## 10. Concurrency & Threading Model

- **Arayüz:** single-threaded JS event loop + Web Workers for heavy pure-UI work (e.g., syntax tokenization). Never blocks on IPC; all IPC is async.
- **Kabuk:** Tokio async runtime. IPC routing, permission checks, and file/shell brokering run on the async runtime; blocking OS calls use a blocking thread pool. One writer task owns the Core Channel stdin; a reader task demultiplexes responses/notifications by id.
- **Çekirdek:** asyncio single event loop for orchestration; CPU/GPU-bound work (embedding, local inference, indexing) dispatched to a bounded worker pool / subprocess to keep the loop responsive. Exactly one task owns stdout writing (framed). See [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md) §concurrency.
- **Cancellation:** every request carries an id; a `$/cancel` notification propagates cancellation cooperatively across tiers. See [10_IPC](./10_IPC.md).

## 11. Directory Structure (Top Level)

Authoritative layout in [37_REPOSITORY_STRUCTURE](./37_REPOSITORY_STRUCTURE.md). Architectural summary:

```
turkish.code/
  apps/desktop/        # Arayüz (src/) + Kabuk (src-tauri/)
  core/                # Çekirdek (Python package turkish_code/)
  packages/
    design-system/     # TTD tokens & components (TS)
    ipc-schema/         # shared IPC contracts, codegen source of truth
  skills/              # first-party Yetenekler
  plugins/             # sample/first-party Eklentiler
  docs/                # this Engineering Bible
  scripts/             # build, package, dev orchestration
  tests/               # cross-tier integration & e2e
```

## 12. Cross-Tier Contracts (Interfaces)

The system is held together by three versioned contracts, all defined once and codegen'd:

1. **Bridge API** — the allowlisted Tauri commands + event names the Arayüz may use. Source of truth: `packages/ipc-schema`. See [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md).
2. **Core Channel API** — the JSON-RPC method set between Kabuk and Çekirdek (`session.*`, `tool.*`, `memory.*`, `workspace.*`, `app.*`, plus notifications). See [10_IPC](./10_IPC.md).
3. **Storage schemas** — DB schemas + event/snapshot formats. See [29_STORAGE](./29_STORAGE.md).

All three are **versioned**; mismatched versions across tiers must be detected at handshake and handled per [10_IPC](./10_IPC.md) §versioning and [33_CONFIGURATION](./33_CONFIGURATION.md) migrations.

## 13. Configuration & Dependencies (Architectural)

- Config is layered (defaults → app → workspace → session), file-based (TOML) plus DB. See [33_CONFIGURATION](./33_CONFIGURATION.md).
- External runtime dependencies are all bundled or optional: SQLite (bundled), local model runtimes (bundled/installed on demand), no mandatory network service. See [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md), [37_REPOSITORY_STRUCTURE](./37_REPOSITORY_STRUCTURE.md).

## 14. Edge Cases (System-Level)

- **Çekirdek fails to start** (missing runtime, port-free but pipe error): Kabuk shows a diagnostic recovery screen; Arayüz remains usable for settings/diagnostics only. See [38_ERROR_HANDLING](./38_ERROR_HANDLING.md).
- **WebView reload mid-run:** Arayüz rehydrates; the in-flight run continues in Çekirdek and re-streams from the last event id. See [26_TIMELINE](./26_TIMELINE.md).
- **Version skew** between a stale WebView bundle and a new Kabuk/Çekirdek: handshake rejects; Kabuk forces reload of the correct bundle.
- **Two windows / workspaces:** each workspace has its own Çekirdek session scope; the process may be shared with per-workspace isolation or one sidecar per workspace (decision in [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md)).
- **Disk full / DB locked:** storage layer surfaces a typed error; no partial timeline writes (journaled). See [29_STORAGE](./29_STORAGE.md).

## 15. Failure Recovery (System-Level)

- Çekirdek crash → supervised restart with exponential backoff; session resumes from the last Checkpoint + Event Journal. See [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md).
- Kabuk crash → OS process dies; on relaunch, unfinished sessions are recoverable from durable storage.
- Corruption of an index/vector store → rebuildable from source (workspace files) without data loss of user code. See [13_RAG_SYSTEM](./13_RAG_SYSTEM.md).
- The **only irreplaceable data** is the user's own files (protected by Snapshots) and their memory/timeline (journaled). Everything else is derived and rebuildable.

## 16. Security (System-Level)

- Single egress choke point (Kabuk) with consent gating → structural privacy. See [30_SECURITY](./30_SECURITY.md).
- No open network ports by default (Core Channel is stdio) → minimal remote attack surface.
- Secrets never cross into Çekirdek storage; the Kabuk injects them only at the moment of an authorized provider call. See [34_API_KEYS](./34_API_KEYS.md).
- The Arayüz is treated as untrusted; the Bridge is an allowlist, not an open RPC. See [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md).

## 17. Performance (System-Level)

- Keep the control plane thin; move bulk to the bulk plane so token streaming never stalls behind a large payload. See [31_PERFORMANCE](./31_PERFORMANCE.md).
- The Arayüz must render first paint without waiting on the Çekirdek (progressive readiness).
- Backpressure is explicit on the stream plane. See [10_IPC](./10_IPC.md).

## 18. Testing Strategy (System-Level)

- **Contract tests** for each of the three cross-tier contracts (generated from `ipc-schema` and storage schemas).
- **Cross-tier integration tests** spinning up a real Kabuk + Çekirdek and driving the canonical lifecycle (§8).
- **Fault-injection tests** for crash recovery (kill the sidecar mid-run and assert resume).
- Details and layering in [35_TESTING](./35_TESTING.md).

## 19. Future Extensions

- **Headless/CLI mode:** run Çekirdek + a thin CLI without the Arayüz for CI/agents (contracts already support this). See [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md).
- **Remote Çekirdek:** optionally run the Core on a trusted GPU box on the LAN via an authenticated channel — must preserve the choke-point and consent model. (Guarded future work; see [43_NON_GOALS](./43_NON_GOALS.md) for the current stance.)
- **Multiple Core instances** for parallel workspaces.

## 20. Anti-Patterns

- Business logic in the Arayüz. (It must be a pure view.)
- The Arayüz reaching the network or filesystem directly.
- Any side effect that bypasses the Kabuk permission engine.
- Opening a TCP port for the Core Channel "for convenience."
- Duplicating authoritative state in more than one tier without labeling it a cache.
- Blocking the Çekirdek event loop with synchronous CPU/GPU work.

## 21. Things That Must Never Happen

1. A file write, shell exec, or network egress occurs without passing the Kabuk permission engine.
2. A file mutation occurs without a preceding Snapshot.
3. The Arayüz obtains a secret or an ambient OS capability.
4. The Core Channel is exposed as a network-listening socket by default.
5. Authoritative AI state lives anywhere but Çekirdek+Storage.

## 22. Relationship With Other Subsystems

This document is referenced by essentially all others. The platform docs ([07](./07_DESKTOP_ARCHITECTURE.md)/[08](./08_TAURI_ARCHITECTURE.md)/[09](./09_PYTHON_BACKEND.md)/[10](./10_IPC.md)) detail the tiers and wires. The intelligence docs ([15](./15_REASONING_ENGINE.md)–[20](./20_TOOL_SYSTEM.md)) live inside the Çekirdek box. The safety/state docs ([24](./24_PERMISSION_SYSTEM.md)–[29](./29_STORAGE.md)) implement the invariants asserted here. Cross-cutting docs ([30](./30_SECURITY.md)–[34](./34_API_KEYS.md)) constrain all tiers.

## 23. Migration Considerations

- The three cross-tier contracts (§12) are versioned; changing any is a migration governed by [10_IPC](./10_IPC.md) and [33_CONFIGURATION](./33_CONFIGURATION.md). Never change a contract silently.
- Swapping a tier's internal tech (e.g., UI framework) must not alter the contracts; that is the whole point of the boundaries.
- Storage migrations are forward-only and journaled; see [29_STORAGE](./29_STORAGE.md).
