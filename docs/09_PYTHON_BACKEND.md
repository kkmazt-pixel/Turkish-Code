# 09 — Python Backend / Core (Çekirdek Mimarisi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner tier:** Çekirdek (Python 3.12+ sidecar)
> **Related:** [01_ARCHITECTURE](./01_ARCHITECTURE.md) · [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) · [10_IPC](./10_IPC.md) · [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) · [29_STORAGE](./29_STORAGE.md) · [36_CODING_STANDARDS](./36_CODING_STANDARDS.md)

---

## 1. Purpose

Specifies the **internal architecture of the Çekirdek** — the Python sidecar that is the AI brain ([01](./01_ARCHITECTURE.md) §4.3). It defines the process entrypoint, the async runtime and concurrency model, the internal module topology and how the intelligence subsystems (docs 11–21) are wired together, dependency-injection, packaging for offline distribution, and the boundary discipline that keeps sensitive side effects brokered by the Kabuk.

## 2. Scope

Process bootstrap and the Core Channel server loop, the asyncio concurrency/worker model, the service/DI container that composes subsystems, request routing to subsystem handlers, packaging/freezing for shipping, and lifecycle. Out of scope: the internals of each intelligence subsystem (their own docs), the wire protocol ([10_IPC](./10_IPC.md)), Python code style ([36_CODING_STANDARDS](./36_CODING_STANDARDS.md)).

## 3. Goals

1. Host **all** AI/business logic in one well-structured, testable Python process.
2. Stay **responsive**: orchestration on a single asyncio loop; heavy CPU/GPU work off-loop.
3. Compose subsystems via **explicit dependency injection** (PR-9) — no import-time globals.
4. Ship **without requiring system Python** (frozen runtime) for offline install (PR-6, [07](./07_DESKTOP_ARCHITECTURE.md)).
5. Never perform brokered side effects directly; request them from the Kabuk ([08](./08_TAURI_ARCHITECTURE.md), [24](./24_PERMISSION_SYSTEM.md)).

### Non-Goals
- No direct OS/UI. No listening network port (transport is stdio, [10](./10_IPC.md)). No secret storage (secrets live in the Kabuk vault, [34](./34_API_KEYS.md)).

## 4. Why Python (Rationale)

- The AI/ML ecosystem (embeddings, tokenizers, local inference bindings, vector libs, RAG tooling) is Python-first — building the brain here is dramatically faster and more capable. Rejected: Rust for the brain (ecosystem immaturity for fast-moving ML), Node (weaker ML libs). The tier boundary ([01](./01_ARCHITECTURE.md)) lets us keep Rust for the trusted broker and Python for intelligence — best tool per tier.

## 5. Process Model & Entry Point

- Launched by the Kabuk supervisor ([08](./08_TAURI_ARCHITECTURE.md) §8) as a child process with stdin/stdout wired to the Core Channel and env carrying paths, locale, log config, and the per-session capability token ([10](./10_IPC.md) §auth). **stdout is reserved exclusively for framed protocol messages**; all logging goes to stderr/log files ([39_LOGGING](./39_LOGGING.md)) — nothing else may write to stdout (a common, fatal mistake; guarded by a stdout guard, §16).
- `__main__.py` sets up the asyncio loop, constructs the DI container (§7), starts the Core Channel server (`kanal/`), performs the handshake, then serves requests until `app.shutdown`.

## 6. Concurrency & Worker Model

```
             ┌───────────────────────── asyncio event loop (single) ─────────────────────────┐
 stdin ─────▶│ kanal.reader → dispatch(request) → subsystem handler (async) → kanal.writer   │──▶ stdout
             │                    │                                                            │
             │                    ├─ awaits I/O (DB, storage) — async, non-blocking            │
             │                    └─ offloads CPU/GPU-bound work ↓                             │
             └───────────────────────────────────────────────────────────────────────────────┘
                                     │
                     ┌───────────────┴──────────────────┐
                     │  Worker pool / subprocess:        │
                     │  embeddings, local inference,     │  (bounded; never blocks the loop)
                     │  indexing, heavy parsing          │
                     └──────────────────────────────────┘
```

- **One event loop** orchestrates everything; it must never block. Rule (PR-14): any operation that can take >~10ms of CPU (embedding, tokenization, local inference, indexing a large tree) is dispatched to a bounded `ProcessPoolExecutor`/subprocess or a runtime that releases the GIL, and awaited.
- **Exactly one writer** owns stdout framing ([10](./10_IPC.md)); handlers enqueue outbound messages/notifications to it (never write stdout directly).
- **Backpressure & cancellation:** each request has an id and a cancellation token; `$/cancel` ([10](./10_IPC.md)) cooperatively cancels the corresponding task tree (including sub-agents, [18](./18_AGENT_SYSTEM.md)). Streams honor consumer backpressure ([10](./10_IPC.md) §backpressure).
- **Bounded everything:** worker pool size, concurrent runs, agent recursion depth, and tool fan-out are all budgeted ([17_EFFORT_MODES](./17_EFFORT_MODES.md), PR-14).

## 7. Composition & Dependency Injection

- A single **DI container** (constructed at boot) wires subsystems together. Each subsystem exposes an interface (Protocol/ABC) and receives its dependencies via constructor injection — no module-level singletons, no import-time side effects (PR-9, [36](./36_CODING_STANDARDS.md)).
- Composition order (dependencies point downward):

```
Config (doc 33)
Storage (doc 29): App/Workspace DB, Blob store, Journal
  └─ Bellek (11), Bilgi Grafı (12), Getirim (13)  ── use Storage + Gömme (14)
Sağlayıcılar (21) [incl. nvidia (22)]  ── provide chat/embedding/rerank
Araçlar (20)  ── request brokered effects via İzin client (24)
Yetenekler (19)  ── packaged capabilities
Çaba (17), Divan (16)  ── policy for Muhakeme
Muhakeme (15)  ── orchestrates: Bellek + Getirim + Araçlar + Sağlayıcılar under Çaba/Divan
Ajanlar (18)  ── compose Muhakeme runs; delegate; scope memory
Zaman (26), Anlık (27), Kurtarma (28)  ── cross-cutting event/state services
kanal (10)  ── exposes the above over the Core Channel
```

- The container is the **only** place that knows the concrete implementations; everything else depends on interfaces (PR-8) — enabling test doubles and provider/storage swaps.

## 8. Request Routing (Core Channel → Subsystem)

- `kanal/` receives a JSON-RPC request ([10](./10_IPC.md)), validates it against the `ipc-schema` contract, resolves the target handler by method namespace (`session.*` → Muhakeme/Ajan; `memory.*` → Bellek; `workspace.*` → Çalışma Alanı; `provider.*` → Sağlayıcılar; `app.*` → lifecycle), attaches the session context (workspace, locale, effort mode, permission context, cancellation token), and invokes the async handler.
- Handlers emit **notifications** (stream plane) for incremental output (reasoning steps, token deltas, tool activity) via the single writer; these become Tauri events in the Kabuk ([08](./08_TAURI_ARCHITECTURE.md) §6).

## 9. The Brokered-Effect Boundary (Critical)

- The Çekirdek performs side effects it *owns* directly: reading/writing its **own** storage (Workspace/App DB, blob store, journal — all inside its data dir), and running the model runtimes it manages.
- Side effects on the **user's world** — writing the user's project files, executing shell, network egress — are **not** done directly. Tools ([20](./20_TOOL_SYSTEM.md)) request them via the **İzin client** (`izin/`) which sends a `tool.invoke`/broker request over the Core Channel; the Kabuk enforces permission, snapshots, and executes ([08](./08_TAURI_ARCHITECTURE.md) §11). This preserves the single choke point (PR-2) and the reversibility guarantee (PR-4).
- **The dividing line, stated once:** *derived AI state and model runtimes → Çekirdek does it; user-world effects and secrets/egress → brokered by Kabuk.* (Storage details: [29](./29_STORAGE.md). Egress-for-cloud-providers: [21](./21_PROVIDER_SYSTEM.md) §egress.)

## 10. Directory Structure

Full tree in [37_REPOSITORY_STRUCTURE](./37_REPOSITORY_STRUCTURE.md) §4 (`core/turkish_code/…`). Each subdirectory is one subsystem, matching its numbered doc. `ortak/` holds shared utilities including the **Turkish locale module** (correct casing/collation for any server-side text; mirrors [03](./03_UI_SYSTEM.md) §11 on the Python side — PR-12). `kanal/` is the Core Channel server. `hata/` defines the typed error hierarchy ([38](./38_ERROR_HANDLING.md)). `gunluk/` is logging ([39](./39_LOGGING.md)).

## 11. Lifecycle

```
spawn (by Kabuk) → build DI container → open Storage → start kanal server
  → handshake (report version, capabilities, providers, models) → [Ready]
  → serve requests (sessions, tools, memory, …) emitting notifications
  → on app.shutdown: cancel in-flight tasks (checkpoint them, doc 28),
     flush journals, close DBs/runtimes, ack, exit
```

Crash behavior and resume: [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md). Supervisor interactions: [08](./08_TAURI_ARCHITECTURE.md) §8.

## 12. State Machine (Per Session, inside Çekirdek)

```
[Created] → [Assembling ctx] → [Reasoning] ⇄ [Awaiting tool/permission]
                                   │                      │
                                   ├──complete──▶ [Done]   │
                                   ├──cancel────▶ [Cancelled]
                                   └──error─────▶ [Failed] (typed, recoverable)
Any state → checkpoint to journal (doc 28) for crash resume.
```

Detailed reasoning states: [15_REASONING_ENGINE](./15_REASONING_ENGINE.md).

## 13. Packaging (Offline Distribution)

- The Çekirdek ships as a **frozen, self-contained runtime** (e.g., PyInstaller/PyOxidizer or a bundled relocatable venv) including Python + all deps + native wheels, placed in the Tauri resources dir ([07](./07_DESKTOP_ARCHITECTURE.md) §6). The user needs **no system Python** (PR-6).
- Native/GPU deps (inference/embedding libs) are bundled per-platform; heavy model **weights are not bundled** (fetched/verified separately, [22](./22_PROVIDER_INTEGRATIONS.md), [32](./32_OFFLINE_FIRST.md)).
- Reproducible builds via pinned `uv.lock` ([33](./33_CONFIGURATION.md)); the frozen bundle is signed as part of the app ([07](./07_DESKTOP_ARCHITECTURE.md) §6).

## 14. Configuration

- Reads layered config ([33_CONFIGURATION](./33_CONFIGURATION.md)) passed/pointed-to by the Kabuk at spawn (paths, locale, effort defaults, provider config sans secrets). Never reads secrets (those are Kabuk-only, injected at egress time — [08](./08_TAURI_ARCHITECTURE.md) §10).

## 15. Dependencies

- Python 3.12+, asyncio, pydantic (schema/validation aligned to `ipc-schema`), a SQLite driver + sqlite-vec ([29](./29_STORAGE.md)), embedding/inference client libs ([14](./14_EMBEDDINGS.md), [22](./22_PROVIDER_INTEGRATIONS.md)), BLAKE3 ([29](./29_STORAGE.md)). All pinned & bundled. No mandatory network dependency (PR-6).

## 16. Edge Cases

- **Something writes to stdout** (a stray `print`, a library banner): corrupts the protocol. Mitigation: at boot, redirect/replace stdout with a guarded stream that raises/logs on unexpected writes, and route all logging to stderr/files ([39](./39_LOGGING.md)). CI lints for `print(`.
- **A subsystem blocks the loop:** guarded by the off-loop worker rule (§6); watchdog logs slow handlers.
- **Worker/subprocess crash** (e.g., an inference segfault): isolated to the worker; the handler returns a typed error and the run degrades/retries (PR-7/PR-10), the loop survives.
- **Corrupt derived store** (index/vector): rebuild from source ([13](./13_RAG_SYSTEM.md)); user code untouched.
- **OOM / GPU OOM:** unload idle models, drop to a smaller model/CPU (degradation ladder, [31](./31_PERFORMANCE.md)); surface a typed error if impossible.
- **Cancellation mid-tool:** propagate to the Kabuk broker so an in-flight brokered op is cooperatively cancelled ([08](./08_TAURI_ARCHITECTURE.md) §15).

## 17. Failure Recovery

- Uncaught handler exception → converted to a typed error response ([38](./38_ERROR_HANDLING.md)), the session marked Failed but recoverable, journal checkpointed ([28](./28_CRASH_RECOVERY.md)).
- Process crash → Kabuk restarts; on boot the Çekirdek reads the journal and offers resume ([28](./28_CRASH_RECOVERY.md)).

## 18. Security

- No listening ports; stdio only ([10](./10_IPC.md)). No secrets in the process ([34](./34_API_KEYS.md)). Treats tool inputs and model outputs as untrusted; all user-world effects are brokered/permissioned (PR-3, §9). Bundled deps are pinned + hash-verified (supply-chain, [30](./30_SECURITY.md)).

## 19. Performance

- Keep the loop free; stream early and often; batch embeddings; cache aggressively (with invalidation) in Bellek/Getirim. Budgets from [17_EFFORT_MODES](./17_EFFORT_MODES.md); measurement in [31_PERFORMANCE](./31_PERFORMANCE.md).

## 20. Testing Strategy

- **Unit tests** per subsystem against interfaces with fakes (the DI container makes this easy).
- **In-process integration**: drive the `kanal` server with recorded Core Channel requests and assert responses/notifications (contract-checked against `ipc-schema`).
- **Determinism harness**: replay a journal and assert reconstructed state ([28](./28_CRASH_RECOVERY.md), PR-15).
- **Loop-safety test**: assert no handler blocks the loop beyond a threshold. See [35_TESTING](./35_TESTING.md).

## 21. Future Extensions

- Headless/CLI embedding of the Çekirdek for agents/CI ([01](./01_ARCHITECTURE.md) §19, [18](./18_AGENT_SYSTEM.md)); a plugin host for out-of-tree tools/providers ([23](./23_PLUGIN_SYSTEM.md)); optional multi-process sharding for parallel workspaces ([25](./25_WORKSPACE_SYSTEM.md)).

## 22. Examples

```python
# __main__.py (illustrative)
async def main() -> None:
    guard_stdout()                          # §16: protocol integrity
    cfg = load_config(env)                  # doc 33
    container = build_container(cfg)         # §7 DI wiring
    server = CoreChannelServer(container)    # doc 10
    await server.handshake()                 # report version/caps
    await server.serve()                     # until app.shutdown
```

## 23. Anti-Patterns

- Writing anything but framed protocol to stdout.
- Import-time side effects / module-level singletons (breaks DI + testing).
- Blocking the event loop with CPU/GPU work.
- Performing user-world side effects directly instead of via the İzin client/broker.
- Storing secrets or opening a network port.
- Unbounded agent recursion / tool loops.

## 24. Things That Must Never Happen

1. Non-protocol data is written to stdout.
2. A user-world side effect (fs write, shell, egress) bypasses the Kabuk broker.
3. A secret is read/stored in the Çekirdek.
4. The event loop is blocked by synchronous heavy work.
5. A subsystem is wired via a global instead of the DI container.

## 25. Relationship With Other Subsystems

Hosts docs 11–21 and 25–28 as internal subsystems; exposes them over [10_IPC](./10_IPC.md) to the Kabuk ([08](./08_TAURI_ARCHITECTURE.md)); persists via [29_STORAGE](./29_STORAGE.md); is orchestrated at the top by [15_REASONING_ENGINE](./15_REASONING_ENGINE.md)/[18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md); coded per [36_CODING_STANDARDS](./36_CODING_STANDARDS.md); errors per [38](./38_ERROR_HANDLING.md); logs per [39](./39_LOGGING.md).

## 26. Migration Considerations

- Internal module refactors are free as long as the Core Channel contract holds (PR-8). Python minor-version bumps and dependency upgrades are validated by the full test suite + determinism harness. Storage/journal format changes are migrations owned by [29](./29_STORAGE.md)/[28](./28_CRASH_RECOVERY.md).
