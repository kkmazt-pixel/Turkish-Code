# 10 — Inter-Process Communication (IPC)

> Part of the **turkish.code Engineering Bible**. Canonical contract document.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** `packages/ipc-schema` (source of truth), Kabuk `channel/`, Çekirdek `kanal/`
> **Related:** [01_ARCHITECTURE](./01_ARCHITECTURE.md) · [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) · [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md) · [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) · [38_ERROR_HANDLING](./38_ERROR_HANDLING.md)

---

## 1. Purpose

Defines the **two IPC links** that connect the three tiers, their transports, framing, message envelopes, method/event catalogs, streaming/cancellation/backpressure semantics, the bulk plane, authentication, versioning/handshake, and error mapping. These contracts are the seams of the whole system ([01](./01_ARCHITECTURE.md) §12); getting them right is the difference between a maintainable system and a tangle. The `packages/ipc-schema` package is the single source of truth from which TS/Rust/Python bindings are generated.

## 2. Scope

The **Bridge** (Arayüz↔Kabuk) and the **Core Channel** (Kabuk↔Çekirdek): transports, framing, envelopes, correlation, streaming, cancellation, backpressure, bulk transfer, auth, versioning, and error semantics. Out of scope: what each method *does* internally (subsystem docs) and permission *policy* ([24](./24_PERMISSION_SYSTEM.md)).

## 3. Goals

1. **No open network ports by default** — offline/security posture ([01](./01_ARCHITECTURE.md) §16, [30](./30_SECURITY.md)).
2. **Typed, versioned, codegen'd contracts** so tiers can't drift (PR-8).
3. **First-class streaming** with cancellation and backpressure for token/reasoning output.
4. **Keep control-plane messages small**; move bulk to a separate plane ([01](./01_ARCHITECTURE.md) §6).
5. Legible to machines (an AI agent can read the schema and call correctly — PR-11).

## 4. Topology

```
Arayüz ──(Bridge: Tauri invoke + events)──▶ Kabuk ──(Core Channel: JSON-RPC/stdio)──▶ Çekirdek
   ◀── Tauri events (re-emitted notifications) ── Kabuk ◀── notifications ── Çekirdek
```

The Kabuk is the router between the two links ([08](./08_TAURI_ARCHITECTURE.md)). The Arayüz never speaks to the Çekirdek directly; the Çekirdek never speaks to the Arayüz directly ([01](./01_ARCHITECTURE.md) §5).

---

## 5. Link A — The Bridge (Arayüz ↔ Kabuk)

- **Transport:** Tauri's built-in IPC — `invoke(command, params)` for request/response, and Tauri **events** for push/streaming. No HTTP, no sockets.
- **Security:** commands are **allowlisted** ([08](./08_TAURI_ARCHITECTURE.md) §7). The WebView cannot call anything not declared. CSP forbids other transports ([03](./03_UI_SYSTEM.md) §13).
- **Typing:** command/event names + param/result/event types are declared in `ipc-schema` and generated into TS (`apps/desktop/src/bridge`) and Rust command signatures.
- **Commands (representative; full set in schema):** `app.bootstrap`, `session.send`, `session.cancel`, `session.resume`, `workspace.open/close/list`, `permission.respond`, `provider.list/test`, `memory.search/pin/forget`, `timeline.query`, `snapshot.restore`, `pref.get/set`. Commands are thin ([08](./08_TAURI_ARCHITECTURE.md) §6).
- **Events (Kabuk → Arayüz):** `reasoning.step`, `token.delta`, `tool.activity`, `permission.request`, `health.change`, `log.line`, `notification`, `run.completed`, `run.failed`, `run.cancelled`. Each carries a `runId`/`sessionId` for correlation and a monotonically increasing `seq` per stream (for gap detection & resume — §9).

---

## 6. Link B — The Core Channel (Kabuk ↔ Çekirdek)

### 6.1 Transport & Framing
- **Transport:** the sidecar's **stdin/stdout pipes**, owned exclusively by the Kabuk ([08](./08_TAURI_ARCHITECTURE.md) §9). **No TCP port.** stderr is logs only ([09](./09_PYTHON_BACKEND.md) §5).
- **Framing:** **length-prefixed** binary framing to delimit messages: a 4-byte big-endian unsigned length header followed by that many bytes of UTF-8 JSON. (Rationale over newline-delimited JSON: payloads may contain newlines; length-prefix is unambiguous and streamable.) One message = one frame.
- **Encoding:** UTF-8 JSON for control/stream planes. (Bulk uses a separate channel, §11.)

### 6.2 Protocol: JSON-RPC 2.0 (profiled)
The Core Channel speaks **JSON-RPC 2.0** with a small profile:

- **Request** (expects a response): `{ "jsonrpc":"2.0", "id": <string uuid>, "method": "<ns.method>", "params": {…}, "meta": {…} }`
- **Response (success):** `{ "jsonrpc":"2.0", "id": <same>, "result": {…} }`
- **Response (error):** `{ "jsonrpc":"2.0", "id": <same>, "error": { "code": <int>, "message": "<tr/en>", "data": { "kind": "<TypedErrorKind>", "retryable": <bool>, "remedy": "…" } } }` — the `data` shape maps to the typed error taxonomy ([38_ERROR_HANDLING](./38_ERROR_HANDLING.md)).
- **Notification** (no response, used for streams & events): `{ "jsonrpc":"2.0", "method":"<ns.event>", "params": {…} }` — has **no `id`**.

**`meta` envelope fields** (present on requests, PR-9 explicitness): `sessionId`, `workspaceId`, `locale` (`tr` default), `effortMode` ([17](./17_EFFORT_MODES.md)), `permissionCtx` (opaque token referencing the session's permission state, [24](./24_PERMISSION_SYSTEM.md)), `traceId` (for the Timeline, [26](./26_TIMELINE.md)), `deadlineMs` (optional budget, PR-14).

### 6.3 Method Namespaces
| Namespace | Direction | Purpose |
|---|---|---|
| `app.*` | K→Ç | `app.handshake`, `app.shutdown`, `app.health` |
| `session.*` | K→Ç | `session.send`, `session.resume`, `session.state` |
| `workspace.*` | K→Ç | open/close/index/status |
| `memory.*` | K→Ç | search/pin/forget ([11](./11_MEMORY_SYSTEM.md)) |
| `timeline.*` | K→Ç | query events ([26](./26_TIMELINE.md)) |
| `provider.*` | K→Ç | list/test/select ([21](./21_PROVIDER_SYSTEM.md)) |
| `tool.*` | **Ç→K** | `tool.invoke` — Çekirdek asks Kabuk to perform a brokered effect ([08](./08_TAURI_ARCHITECTURE.md) §11, [20](./20_TOOL_SYSTEM.md)) |
| `permission.*` | **Ç→K / K→Ç** | request/decision flow ([24](./24_PERMISSION_SYSTEM.md)) |
| `$/…` | both | protocol control: `$/cancel`, `$/progress`, `$/log` |

Note the Core Channel is **bidirectional**: while most requests are Kabuk→Çekirdek, tool execution and permission requests flow **Çekirdek→Kabuk** as JSON-RPC requests in the other direction (the Çekirdek is a client too). Both sides implement request + response + notification.

---

## 7. Correlation & Concurrency

- Every request carries a unique `id` (UUIDv4). Responses match by `id`. Multiple requests may be in flight concurrently on both links; there is no head-of-line blocking (the reader demuxes by `id`/`method`, [08](./08_TAURI_ARCHITECTURE.md) §9, [09](./09_PYTHON_BACKEND.md) §6).
- Notifications for a stream carry the originating request's `runId`/`sessionId` plus a per-stream monotonic `seq` (§9).

## 8. Streaming Semantics (the Stream Plane)

- Streaming output (token deltas, reasoning steps, tool activity, progress) is sent as **notifications** correlated to the initiating request's `runId`, **before** the final response. The final response marks completion (or `run.failed`/`run.cancelled`).
- Order within a stream is guaranteed by transport (single ordered pipe) and made explicit with `seq`.
- The Kabuk re-emits each Core Channel notification as a Bridge event ([08](./08_TAURI_ARCHITECTURE.md) §6) with the same `runId`/`seq`, letting the Arayüz reconstruct the stream and detect gaps.
- **Resume:** on WebView reload or Çekirdek restart, the Arayüz calls `session.resume` with the last `seq` it saw; the Çekirdek replays missed events from the journal ([26](./26_TIMELINE.md), [28](./28_CRASH_RECOVERY.md)) so no output is lost ([03](./03_UI_SYSTEM.md) §6.3).

## 9. Backpressure

- **Bounded queues** on every hop (Çekirdek writer queue, Kabuk re-emit queue). If a downstream consumer is slower than the producer, the producer applies backpressure by awaiting queue capacity (never unbounded buffering — PR-14).
- **Coalescing:** high-frequency `token.delta` notifications may be coalesced by the producer into batched frames (e.g., per few ms) to bound message rate; the Arayüz further coalesces per animation frame ([03](./03_UI_SYSTEM.md) §9, [05](./05_ANIMATION_SYSTEM.md) §6). Coalescing merges data; it never drops data.
- The Çekirdek's generation loop yields to backpressure so a stalled UI can't OOM the pipe.

## 10. Cancellation

- `$/cancel { runId }` is a notification sent by the requester (Arayüz→Kabuk via `session.cancel`, then Kabuk→Çekirdek as `$/cancel`).
- Cancellation is **cooperative**: the Çekirdek propagates it to the task tree (reasoning loop, sub-agents [18](./18_AGENT_SYSTEM.md), in-flight tool calls), and in-flight brokered ops in the Kabuk are cancelled too ([08](./08_TAURI_ARCHITECTURE.md) §15). The run ends with `run.cancelled`. Partial file writes are protected by pre-write snapshots ([27](./27_SNAPSHOTS.md)).
- Idempotent: cancelling an already-finished run is a no-op.

## 11. The Bulk Plane

- **Rule:** large binary payloads (file contents beyond a threshold, embeddings blobs, snapshot data) **never** travel inside JSON control/stream frames — they would bloat and stall the control plane ([01](./01_ARCHITECTURE.md) §6).
- **Mechanisms (in priority order):**
  1. **Blob reference:** the producer writes to the content-addressed Blob Store ([29](./29_STORAGE.md)) and passes a `{ blobRef: "<blake3>" }` in the JSON; the consumer reads the blob directly. Preferred for anything persisted anyway (snapshots, large tool outputs).
  2. **Bulk channel:** an optional **Unix domain socket / Windows named pipe** (still no TCP) between Kabuk and Çekirdek for streaming large transient bytes, referenced by a handle in the JSON. Used when data isn't a persisted blob.
- Thresholds and the exact handoff are configured ([33](./33_CONFIGURATION.md)); default inline limit is small (e.g., 32 KiB).

## 12. Authentication (Core Channel)

- Although the Core Channel is a private stdio pipe (not networked), the Çekirdek requires a **per-session capability token** (a random secret) passed in env at spawn ([08](./08_TAURI_ARCHITECTURE.md) §8) and echoed in `app.handshake`. This defends against a stray process attaching to a leaked pipe/UDS and is required for the optional bulk UDS/named pipe (which *does* have a filesystem presence). The token is **not** a user secret and never touches the Arayüz.

## 13. Versioning & Handshake

- Each contract (Bridge, Core Channel) has a **semantic version** embedded in `ipc-schema`.
- **Handshake** (`app.handshake`, first message): exchanges `protocolVersion`, `coreVersion`, `capabilities`, available `providers`/`models`, and the auth token. The Kabuk verifies compatibility:
  - **Compatible (same major):** proceed; unknown optional fields ignored (forward-compat).
  - **Incompatible (major mismatch):** refuse; the Kabuk surfaces a clear error and (for a stale Arayüz bundle) forces a reload of the correct assets ([01](./01_ARCHITECTURE.md) §14, [08](./08_TAURI_ARCHITECTURE.md) §15).
- **Evolution rules (PR-18):** additive changes (new optional params, new methods, new notification types) are minor/backward-compatible; removals/renames/semantic changes are major and require a migration note. Consumers must ignore unknown notification types gracefully ([06](./06_COMPONENT_LIBRARY.md) §12, [03](./03_UI_SYSTEM.md)).

## 14. Error Mapping

- Transport/protocol errors (bad frame, invalid JSON-RPC) use reserved JSON-RPC codes and trigger a protocol-error path (repeated protocol errors → treat sidecar as crashed, [08](./08_TAURI_ARCHITECTURE.md) §15).
- **Application errors** are returned as JSON-RPC `error` objects whose `data.kind` maps to the typed error taxonomy ([38_ERROR_HANDLING](./38_ERROR_HANDLING.md)); `data.retryable` and `data.remedy` let the caller decide (PR-10). The Kabuk surfaces user-facing errors via the `notification`/`run.failed` events with Turkish-localized messages ([04](./04_TURKISH_DESIGN_LANGUAGE.md) §12, [38](./38_ERROR_HANDLING.md)).
- Timeouts: `deadlineMs` in `meta` bounds a request; exceeding it yields a typed timeout error and cancellation of the task.

## 15. Configuration

- Inline-bulk threshold, coalescing window, queue bounds, heartbeat interval, handshake timeout, and restart backoff are configurable ([33_CONFIGURATION](./33_CONFIGURATION.md)) with safe defaults.

## 16. Dependencies

- `packages/ipc-schema` (JSON Schema + codegen), Tauri IPC (Bridge), serde_json/Tokio (Kabuk), pydantic/asyncio (Çekirdek). No network libs required for the default transport.

## 17. Edge Cases

- **Interleaved streams** from concurrent runs: disambiguated by `runId`; the Arayüz maintains per-run buffers ([03](./03_UI_SYSTEM.md) §6.2).
- **Notification arrives after final response** (late tool log): consumers accept trailing notifications up to a grace window keyed by `runId`, then drop with a debug log.
- **Huge single tool result** (e.g., a 200MB file read): forced onto the bulk plane (§11); never inlined.
- **Pipe closed unexpectedly** (sidecar died): reader detects EOF → supervisor recovery ([08](./08_TAURI_ARCHITECTURE.md) §8).
- **Clock/`seq` reset after restart:** `seq` is per-run and journaled; resume uses journaled `seq` ([28](./28_CRASH_RECOVERY.md)).
- **Unknown method/notification** (version skew within same major): respond with method-not-found (requests) or ignore (notifications) — never crash.

## 18. Failure Recovery

- Protocol desync → drop the connection, restart sidecar, resume sessions from journal ([28](./28_CRASH_RECOVERY.md)).
- Lost stream → `session.resume` replays from last `seq` (§8).
- These recovery paths are exercised by fault-injection tests (§20).

## 19. Security

- No default network port ([01](./01_ARCHITECTURE.md) §16). The bulk UDS/named pipe (when used) is created with restrictive permissions and guarded by the capability token (§12). Secrets **never** traverse the Core Channel to the Çekirdek ([08](./08_TAURI_ARCHITECTURE.md) §10, [34](./34_API_KEYS.md)). All method params are schema-validated on receipt (reject malformed). See [30_SECURITY](./30_SECURITY.md).

## 20. Testing Strategy

- **Contract tests** generated from `ipc-schema`: round-trip every message type across TS/Rust/Python.
- **Streaming tests:** ordering, `seq` gap detection, backpressure (slow consumer doesn't drop/OOM), coalescing correctness (no data loss).
- **Cancellation tests:** `$/cancel` stops the task tree and brokered ops; run ends `cancelled`.
- **Resume tests:** kill sidecar mid-stream; `session.resume` replays exactly.
- **Version tests:** mismatched majors refuse; minor forward-compat ignores unknowns. See [35_TESTING](./35_TESTING.md).

## 21. Future Extensions

- An optional authenticated **remote Core Channel** (LAN GPU box) — would reuse the same JSON-RPC envelope over a TLS+token transport while preserving the choke-point/consent model ([01](./01_ARCHITECTURE.md) §19; gated by [43_NON_GOALS](./43_NON_GOALS.md)). A CLI client speaking the Core Channel directly for headless/agent use ([18](./18_AGENT_SYSTEM.md)).

## 22. Examples

**Start a run (Bridge → Core Channel):**
```jsonc
// Arayüz: invoke("session.send", { sessionId, text, effortMode: "dengeli" })
// Kabuk → Çekirdek frame (len-prefixed):
{ "jsonrpc":"2.0","id":"9f..","method":"session.send",
  "params":{"text":"README'yi güncelle"},
  "meta":{"sessionId":"s1","workspaceId":"w1","locale":"tr",
          "effortMode":"dengeli","permissionCtx":"pc-…","traceId":"t-…"} }
```
**Streamed step (Çekirdek → Kabuk → Arayüz):**
```jsonc
{ "jsonrpc":"2.0","method":"reasoning.step",
  "params":{"runId":"r1","seq":7,"kind":"plan","text":"…"} }
```
**Tool request (Çekirdek → Kabuk), permissioned + snapshotted:**
```jsonc
{ "jsonrpc":"2.0","id":"a1","method":"tool.invoke",
  "params":{"name":"fs.write","args":{"path":"README.md","contentRef":"blake3:…"}},
  "meta":{"sessionId":"s1","permissionCtx":"pc-…"} }
```

## 23. Anti-Patterns

- Putting large binary blobs inside JSON frames.
- The Arayüz talking to the Çekirdek directly (must route via Kabuk).
- Hand-writing bindings instead of codegen from `ipc-schema`.
- Unbounded buffering of stream notifications (must apply backpressure).
- Silent, incompatible contract changes (must version + migrate).
- Sending secrets over the Core Channel.

## 24. Things That Must Never Happen

1. A default-on TCP listening port is opened for IPC.
2. A secret is transmitted to the Çekirdek over the Core Channel.
3. Bulk binary data is inlined into control/stream JSON frames.
4. Contract bindings are hand-edited or allowed to drift from `ipc-schema`.
5. A stream drops data under backpressure (coalesce, don't drop).

## 25. Relationship With Other Subsystems

Realizes the seams of [01](./01_ARCHITECTURE.md); implemented by [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) (Kabuk side) and [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md) (Çekirdek side); carries permission/tool flows for [24](./24_PERMISSION_SYSTEM.md)/[20](./20_TOOL_SYSTEM.md); carries streaming for [15](./15_REASONING_ENGINE.md)/[16](./16_COUNCIL_MODE.md); resume relies on [26](./26_TIMELINE.md)/[28](./28_CRASH_RECOVERY.md); errors per [38](./38_ERROR_HANDLING.md); bulk via [29](./29_STORAGE.md).

## 26. Migration Considerations

- Contracts are semver'd in `ipc-schema`; additive changes are minor, breaking changes are major with a migration note and a deprecation window (PR-18). Codegen + a CI drift check keep all three tiers in lockstep ([37](./37_REPOSITORY_STRUCTURE.md) §7).
