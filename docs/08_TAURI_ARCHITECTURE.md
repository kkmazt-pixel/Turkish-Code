# 08 — Tauri / Shell Architecture (Kabuk Mimarisi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner tier:** Kabuk (Rust / Tauri 2.x)
> **Related:** [01_ARCHITECTURE](./01_ARCHITECTURE.md) · [07_DESKTOP_ARCHITECTURE](./07_DESKTOP_ARCHITECTURE.md) · [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md) · [10_IPC](./10_IPC.md) · [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) · [34_API_KEYS](./34_API_KEYS.md)

---

## 1. Purpose

Specifies the **internals of the Kabuk**: the Rust/Tauri process that is the trusted broker and the single choke point for all side effects ([01](./01_ARCHITECTURE.md) §4.2). It defines the Bridge API surface, the Çekirdek supervisor, the Core Channel client, the permission-enforcement locus, the secret vault, and the brokered side-effect implementations. If [01](./01_ARCHITECTURE.md) is the map, this is the detailed schematic of the most-trusted box.

## 2. Scope

Rust module layout, Tauri capability/allowlist model, Bridge commands & events, the sidecar supervisor state machine, the Core Channel transport client, the permission engine's enforcement point, the secret vault, and the broker (fs/shell/net). Out of scope: the wire format details ([10_IPC](./10_IPC.md)), permission *policy* ([24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) owns the model; here we own enforcement mechanics), Python internals ([09](./09_PYTHON_BACKEND.md)).

## 3. Goals

1. Be **small, auditable, statically-typed** — the tier we trust most stays minimal.
2. Enforce the two structural invariants: **every side effect passes here** ([01](./01_ARCHITECTURE.md) §21) and **secrets never leave here in plaintext** ([30](./30_SECURITY.md)).
3. Supervise the Çekirdek robustly (spawn, health, restart, recover).
4. Expose a **narrow, allowlisted** Bridge to the untrusted Arayüz.

### Non-Goals
- No AI/business logic (that is Çekirdek). No UI (that is Arayüz). Rust here is plumbing + policy enforcement, nothing more.

## 4. Why Tauri (Rationale)

- Small binaries, OS-native WebView (no bundled Chromium) → fast, light, better for offline distribution ([07](./07_DESKTOP_ARCHITECTURE.md)).
- Rust core → memory-safe trusted broker with a capability/permission system suited to our choke-point design.
- First-class sidecar management → clean supervision of the Python Çekirdek.
- Rejected: Electron (heavy, Node in the trusted tier, weaker privilege separation), native-per-OS (triples UI work). See [01](./01_ARCHITECTURE.md) §4.4.

## 5. Module Layout

```
apps/desktop/src-tauri/src/
  main.rs           # app setup, plugin registration, window creation
  commands/         # Bridge API — allowlisted #[tauri::command] fns (thin)
  supervisor/       # Çekirdek lifecycle: spawn, health, restart, recover
  channel/          # Core Channel client (framing, correlation, streaming)
  permission/       # ENFORCEMENT point (policy lives in doc 24)
  secrets/          # OS keychain vault; secret injection at call time
  broker/           # THE side-effect implementations:
     fs.rs          #   permissioned file read/write (+ snapshot hook)
     shell.rs       #   permissioned process execution
     net.rs         #   permissioned network egress (the ONLY egress path)
  events/           # re-emit Core Channel notifications → Tauri events
  state.rs          # app state (handles, config, health), Tauri managed state
capabilities/       # Tauri capability manifests (Bridge allowlist)
tauri.conf.json
```

**Rule (PR-2):** the raw OS primitives for file write, process spawn, and socket/HTTP egress appear **only** inside `broker/`. `grep` must confirm this. Everything else calls the broker.

## 6. The Bridge API (Arayüz ↔ Kabuk)

- Implemented as Tauri commands (`invoke`) + Tauri events (push). The **allowlist is the security boundary** ([01](./01_ARCHITECTURE.md) §5): only declared commands exist; the Arayüz cannot call arbitrary Rust.
- Command definitions are declared in `packages/ipc-schema` and codegen'd to TS types (Arayüz) and Rust signatures (Kabuk) so the contract can't drift ([37](./37_REPOSITORY_STRUCTURE.md), [10](./10_IPC.md)).
- Commands are **thin**: validate input, attach the session's permission context, and forward to the Çekirdek over the Core Channel (or perform a purely-Kabuk operation like reading a trivial pref). No business logic.

Representative Bridge surface (full list in `ipc-schema`):

| Command | Purpose | Delegates to |
|---|---|---|
| `app.bootstrap` | locale, theme, health, last workspace | Kabuk (+ Çekirdek status) |
| `session.send` | send a message / start a run | Çekirdek `session.send` |
| `session.cancel` | interrupt a run | Çekirdek `$/cancel` |
| `session.resume` | rehydrate after reload/crash | Çekirdek + journal |
| `workspace.open` | open a folder as workspace | Çekirdek `workspace.open` |
| `permission.respond` | user's answer to a prompt | permission engine |
| `provider.list` / `provider.test` | provider status | Çekirdek `provider.*` |
| `pref.get/set` | trivial view prefs | Kabuk (config) |

**Events** (Kabuk → Arayüz): `reasoning.step`, `token.delta`, `tool.activity`, `permission.request`, `health.change`, `log.line`, `notification`. These are re-emitted from Core Channel notifications ([10](./10_IPC.md)).

## 7. Tauri Capability / Allowlist Model

- Tauri's capability system is configured to **deny by default**. The Arayüz WebView is granted only: our custom Bridge commands, and the minimum Tauri APIs it needs (e.g., events). Dangerous built-ins (raw fs, shell, http) are **disabled** for the WebView — the WebView must go through *our* brokered commands so permission gating applies. ([01](./01_ARCHITECTURE.md) §5, [30](./30_SECURITY.md)).
- The CSP is set here too (coordinated with [03](./03_UI_SYSTEM.md) §13): no remote origins; `connect-src` limited to the IPC scheme.
- Capability manifests live in `capabilities/` and are reviewed like security policy.

## 8. Çekirdek Supervisor

Owns the sidecar's lifecycle. State machine (also in [01](./01_ARCHITECTURE.md) §9, detailed here):

```
[Stopped] --spawn--> [Starting] --handshake ok--> [Ready]
   ^                     |handshake fail/timeout      | crash/heartbeat miss
   |                     v                            v
   +--- stop ------- [Failed] <--backoff-- [Recovering] --ok--> [Ready]
                       (max N restarts in window → surface fatal to user)
```

- **Spawn:** launch the bundled Çekirdek binary/runtime ([09](./09_PYTHON_BACKEND.md)) with stdin/stdout wired for the Core Channel and env carrying: app-data paths ([07](./07_DESKTOP_ARCHITECTURE.md) §5), locale, the **per-session capability token** ([10](./10_IPC.md) §auth), and log config. **No secrets in env** (secrets are injected per-call, §10).
- **Handshake:** exchange versions/capabilities ([01](./01_ARCHITECTURE.md) §12, [10](./10_IPC.md) §versioning). Mismatch → refuse and inform the user.
- **Health:** periodic heartbeat over the Core Channel; missed heartbeats or a dead pipe → Recovering.
- **Restart & recover:** exponential backoff, bounded retries; on restart, coordinate session resume with [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md). After N failures in a window, present a fatal diagnostic ([38](./38_ERROR_HANDLING.md)) rather than crash-looping.
- **Shutdown:** send `app.shutdown`, await flush with timeout, then terminate; force-kill if unresponsive.

## 9. Core Channel Client

- Implements the Kabuk side of the JSON-RPC-over-stdio transport defined in [10_IPC](./10_IPC.md): one writer task owns stdin; one reader task demuxes responses (by id) and notifications (by method) → routes notifications to `events/` for re-emission.
- Handles correlation, timeouts, cancellation (`$/cancel`), and backpressure ([10](./10_IPC.md)). The **bulk plane** (large payloads over UDS/named pipe or blob refs) is also managed here ([01](./01_ARCHITECTURE.md) §6).
- The channel is the *only* thing that talks to the Çekirdek; nothing else in the Kabuk holds the pipes.

## 10. Secret Vault & Injection

- Secrets (API keys, [34_API_KEYS](./34_API_KEYS.md)) live in the **OS keychain**, accessed only by `secrets/`. They are **never** written to SQLite, config files, logs, or env, and **never** sent to the Arayüz ([01](./01_ARCHITECTURE.md) §16, [30](./30_SECURITY.md)).
- **Injection model:** when the Çekirdek needs to make an authenticated provider call that requires egress, it asks the Kabuk to perform the egress via `broker/net.rs`; the Kabuk retrieves the secret from the vault, attaches it to the outgoing request, performs the (consent-gated) call, and returns the response. Thus the secret is used **inside the trusted tier** and the Çekirdek never sees the raw key. (For fully-local providers there is no secret and no egress.) Details and the exact division for streaming provider calls: [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) §"egress via Kabuk", [34_API_KEYS](./34_API_KEYS.md).

## 11. Permission Enforcement Locus

- The **policy/model** (modes, capabilities, consent) is [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md). The **enforcement** happens here: every brokered side-effect call (`broker/*`) first passes `permission/` which evaluates the active session's mode + grants + the specific target, and either allows, denies, or raises a `permission.request` event to the user and awaits `permission.respond`.
- Because all side effects funnel through the broker, and the broker calls the permission engine first, enforcement is **structurally unavoidable** (PR-1/PR-2). This is the crux of Pillar P5.
- On an allowed file mutation, the broker triggers a **Snapshot** ([27](./27_SNAPSHOTS.md)) *before* writing and appends a **Timeline event** ([26](./26_TIMELINE.md)) — both are mandatory hooks in `broker/fs.rs`.

## 12. Data Flow (Bridge → Broker)

```
Arayüz.invoke("session.send") 
  → commands/session.rs (validate, attach perm ctx)
  → channel → Çekirdek runs reasoning
  → Çekirdek requests tool.invoke("fs.write", ...) over Core Channel
  → channel → permission/ (evaluate) → [maybe permission.request → Arayüz → respond]
  → broker/fs.rs: snapshot → write → timeline event
  → result back over channel → Çekirdek observes → continues
```

## 13. Configuration

- Reads app config ([33_CONFIGURATION](./33_CONFIGURATION.md)) at boot: paths, providers, permission defaults, update policy, log level. Privacy-relevant defaults are the most-private ([30](./30_SECURITY.md)).
- `tauri.conf.json` + `capabilities/` hold the static app/security config.

## 14. Dependencies

- Tauri 2.x, Tokio, serde/serde_json, an OS-keychain crate, a subprocess/pty crate for `shell.rs`. All vendored/pinned ([33](./33_CONFIGURATION.md)). No network service dependency.

## 15. Edge Cases

- **Çekirdek writes malformed frames:** the channel rejects and, on repeated protocol errors, restarts the sidecar (treat as crash).
- **Permission prompt while Arayüz is closed/unfocused:** raise an OS notification ([07](./07_DESKTOP_ARCHITECTURE.md)); if no UI can answer, default to **deny** (fail-safe, [24](./24_PERMISSION_SYSTEM.md)).
- **Broker op cancelled mid-flight:** cooperative cancellation; a partially-written file is protected by the pre-write snapshot ([27](./27_SNAPSHOTS.md)).
- **Keychain locked/unavailable:** surface a typed error; degrade to no-cloud (local-only) rather than storing secrets insecurely ([34](./34_API_KEYS.md), PR-7).
- **Version skew** with a stale Arayüz bundle: reject at bootstrap, force correct bundle.

## 16. Failure Recovery

- Sidecar crash → supervisor restart + [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md). Kabuk crash → OS kills the process group; on relaunch, durable storage enables resume ([01](./01_ARCHITECTURE.md) §15).
- The supervisor guarantees no orphaned Çekirdek processes (process-group ownership / kill-on-parent-exit).

## 17. Security

- Deny-by-default capabilities; strict CSP; secrets sealed in the vault; single egress path; no listening ports; child process ownership. This module *is* much of [30_SECURITY](./30_SECURITY.md)'s implementation. It is intentionally small so it can be fully audited.

## 18. Performance

- The Kabuk is not on the model hot path; its job is low-latency routing. Streaming re-emission must be zero-copy-ish and non-blocking (one reader task, bounded channels). Backpressure per [10](./10_IPC.md). Metrics in [31](./31_PERFORMANCE.md).

## 19. Testing Strategy

- **Rust unit tests** for permission evaluation, framing/correlation, secret vault, and broker gating (assert every broker op consults permission + snapshots on mutate).
- **Supervisor fault-injection**: kill the sidecar, assert clean restart/recover and no orphans.
- **Contract tests** against `ipc-schema` for the Bridge and Core Channel.
- **Security tests**: assert the WebView cannot invoke non-allowlisted commands or reach raw fs/net; assert secrets never appear in logs/events. See [35_TESTING](./35_TESTING.md), [30_SECURITY](./30_SECURITY.md).

## 20. Future Extensions

- A headless Kabuk mode (no window) for CLI/agent operation ([01](./01_ARCHITECTURE.md) §19); pluggable brokers for new capability classes (all still funneling through permission + timeline).

## 21. Examples

```rust
// broker/fs.rs — the ONLY file-write path (illustrative)
pub async fn write_file(ctx: &SessionCtx, path: &Path, bytes: &[u8]) -> Result<(), BrokerError> {
    permission::require(ctx, Capability::FsWrite, Target::path(path)).await?; // doc 24
    snapshot::before_mutation(ctx, path).await?;                              // doc 27
    let res = fs::write(path, bytes).await;                                   // the raw primitive
    timeline::append(ctx, Event::file_write(path, res.is_ok())).await;        // doc 26
    res.map_err(BrokerError::from)
}
```

## 22. Anti-Patterns

- Business logic creeping into commands or the broker.
- A raw OS side-effect primitive outside `broker/`.
- Putting secrets in env, logs, config, or the Core Channel to the Çekirdek.
- Broadening the capability allowlist "for convenience."
- Skipping the snapshot/timeline hooks on a mutating broker op.

## 23. Things That Must Never Happen

1. A side effect executes without passing `permission/`.
2. A file mutation executes without a preceding snapshot + timeline event.
3. A secret reaches the Arayüz, the Çekirdek's storage, or a log.
4. A non-allowlisted command is invokable by the WebView.
5. An orphaned Çekirdek process survives Kabuk exit.

## 24. Relationship With Other Subsystems

Implements the trusted-broker tier of [01](./01_ARCHITECTURE.md); hosts the desktop integration of [07](./07_DESKTOP_ARCHITECTURE.md); supervises the brain of [09](./09_PYTHON_BACKEND.md) over the transport of [10](./10_IPC.md); enforces [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md); triggers [27_SNAPSHOTS](./27_SNAPSHOTS.md)/[26_TIMELINE](./26_TIMELINE.md); guards secrets for [34_API_KEYS](./34_API_KEYS.md); realizes [30_SECURITY](./30_SECURITY.md).

## 25. Migration Considerations

- The Bridge and Core Channel contracts are versioned ([10](./10_IPC.md)); capability manifest changes are security-reviewed. Tauri major upgrades are treated as platform migrations with full E2E re-verification ([35](./35_TESTING.md)).
