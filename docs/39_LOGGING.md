# 39 — Logging & Observability (Günlükleme)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** cross-cutting (Çekirdek `gunluk/`, Kabuk logging, Arayüz log bridge)
> **Related:** [38_ERROR_HANDLING](./38_ERROR_HANDLING.md) · [26_TIMELINE](./26_TIMELINE.md) · [30_SECURITY](./30_SECURITY.md) · [34_API_KEYS](./34_API_KEYS.md) · [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md)

---

## 1. Purpose

Defines **logging and local observability**: structured, leveled logs for diagnostics and support, kept strictly local and secret-free. Logging is for *developers/support diagnosing behavior*; it is distinct from the **Timeline** ([26](./26_TIMELINE.md)), which is the *user-facing, product-level audit of what the agent did*. This doc specifies levels, formats, sinks, redaction, rotation, and the critical rule that in the Çekirdek **logs never go to stdout** (which is the IPC channel).

## 2. Scope

Log levels, structured format, per-tier sinks, correlation with runs/sessions, redaction, rotation/retention, and log-vs-Timeline distinction. Out of scope: the product audit log ([26_TIMELINE](./26_TIMELINE.md)), error semantics ([38](./38_ERROR_HANDLING.md)), telemetry (there is none by default — [30](./30_SECURITY.md)).

## 3. Goals

1. **Diagnose without leaking**: enough structured detail to debug, with **zero secrets** and privacy respected ([30](./30_SECURITY.md)/[34](./34_API_KEYS.md)).
2. **Local only**: logs stay on disk; sending them anywhere is egress → consented, never automatic ([30](./30_SECURITY.md), PR-16).
3. **Correlatable**: logs carry run/session/trace ids to line up with the Timeline ([26](./26_TIMELINE.md)) and IPC ([10](./10_IPC.md)).
4. **Protocol-safe**: in the Çekirdek, stdout is sacred (IPC) — logs go to stderr/files only ([09](./09_PYTHON_BACKEND.md) §5/§16).
5. **Bounded**: rotation/retention so logs never fill the disk (PR-14).

### Non-Goals
- Not the product audit trail ([26](./26_TIMELINE.md)). Not remote telemetry/crash-reporting-by-default. Not user-facing (users see the Timeline + errors, not logs).

## 4. Log vs Timeline (Critical Distinction)

| | **Log ([39](./39_LOGGING.md))** | **Timeline ([26](./26_TIMELINE.md))** |
|---|---|---|
| Audience | developer/support | the user |
| Content | technical diagnostics | what the agent did (messages/tools/edits/decisions) |
| Durability | rotated/ephemeral | durable, append-only, recovery substrate |
| Location | stderr/log files | Event Journal + projection ([29](./29_STORAGE.md)) |
| In recovery? | no | yes (source of truth) |

They serve different purposes and are **not** interchangeable ([44](./44_GLOSSARY.md) forbids conflating "log" with "Timeline"). A tool call appears in *both*: a rich diagnostic line in the log, and a user-facing event in the Timeline.

## 5. Levels

Standard leveled logging: `TRACE` < `DEBUG` < `INFO` < `WARN` < `ERROR`. Default level `INFO` (config, [33](./33_CONFIGURATION.md)); `DEBUG`/`TRACE` opt-in for diagnostics. `ERROR` lines correspond to typed `AppError`s ([38](./38_ERROR_HANDLING.md)) with their `code`/`kind` (not raw stack dumps to users; stacks live in logs at `ERROR`/`DEBUG`).

## 6. Structured Format

- **Structured (JSON lines or key-value)** for machine parsing (PR-11): `{ts, level, tier, module, msg, sessionId?, runId?, traceId?, errKind?, code?, ...fields}`.
- **Correlation ids** (`sessionId`/`runId`/`traceId`) tie a log line to a Timeline run ([26](./26_TIMELINE.md)) and an IPC request ([10](./10_IPC.md)) — so support can follow one operation across all three tiers.
- Human-readable console formatting in dev; structured in files/production.

## 7. Sinks Per Tier

- **Çekirdek:** logs to **stderr** and to rotating **log files** in `DATA_DIR/logs/core/` — **never stdout** ([09](./09_PYTHON_BACKEND.md) §5). A stdout guard prevents accidental writes.
- **Kabuk:** logs to files in `DATA_DIR/logs/shell/` (+ stderr in dev). The Kabuk also *collects* the Çekirdek's stderr for a unified view.
- **Arayüz:** logs route via the Bridge to the Kabuk (a `log.line` path) so all logs land in one place; the browser console is dev-only. The Arayüz never writes files directly ([03](./03_UI_SYSTEM.md)).
- A **unified log view** (dev/diagnostics UI) can stream `log.line` events ([08](./08_TAURI_ARCHITECTURE.md) §6) for live debugging.

## 8. Redaction (Non-Negotiable)

- A **redaction filter** runs on every log record: scrubs anything matching secret patterns (keys/tokens), and never logs known-sensitive fields (auth headers, secret values) — secrets structurally never reach loggable paths outside the Kabuk call site, which does not log them ([34](./34_API_KEYS.md)/[30](./30_SECURITY.md) §7).
- **User content** (code, prompts) is logged sparingly and at higher verbosity levels only; at `INFO` and below, log *metadata* (sizes, ids, counts), not raw sensitive content, to respect privacy even locally.
- CI secret-scanning also checks log fixtures/outputs ([35](./35_TESTING.md)).

## 9. Rotation & Retention

- **Rotation** by size/age; **retention** bounded (config, [33](./33_CONFIGURATION.md)) so logs never fill the disk (PR-14). Old logs are deleted, not archived off-device (no egress). A crash report bundle can be assembled **on demand** (user action) for support — its export is a consented egress or a local file the user shares manually ([30](./30_SECURITY.md)).

## 10. Directory Structure

```
core/turkish_code/gunluk/   # structured logger, redaction filter, stdout guard
apps/desktop/src-tauri/…    # Kabuk logging + Çekirdek stderr collection + log.line emit
apps/desktop/src/…          # Arayüz → Bridge log routing
DATA_DIR/logs/{core,shell}/ # rotating log files
```

## 11. Configuration

- Log level (global + per-module), format (json/console), file rotation/retention, and redaction rules are configurable ([33](./33_CONFIGURATION.md)); privacy-respecting defaults (INFO, redaction on, local-only). No log egress without consent.

## 12. Dependencies

- [38_ERROR_HANDLING](./38_ERROR_HANDLING.md) (ERROR lines from typed errors), [26_TIMELINE](./26_TIMELINE.md) (distinct; correlation ids), [10_IPC](./10_IPC.md)/[08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) (log.line routing), [34_API_KEYS](./34_API_KEYS.md)/[30_SECURITY](./30_SECURITY.md) (redaction), [29_STORAGE](./29_STORAGE.md) (log dir), [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md) (stdout discipline).

## 13. Edge Cases

- **Accidental stdout write in Çekirdek:** the stdout guard ([09](./09_PYTHON_BACKEND.md) §16) intercepts/redirects it to the log + raises in dev; CI bans `print(` ([36](./36_CODING_STANDARDS.md)).
- **Log volume explosion** (a tight loop logging): rate-limiting/sampling for hot log sites; rotation bounds disk.
- **Secret in a would-be log line:** redaction strips it; if a new secret shape appears, the pattern set is updated (defense in depth).
- **Disk full:** logging degrades (drops low-priority lines) rather than blocking the app; never fails a user operation because of logging.
- **Multi-workspace/multi-window:** correlation ids + tier tags disambiguate interleaved logs.
- **Third-party lib chatty logging:** captured and leveled through our logger (not raw to stdout).

## 14. Failure Recovery

- Logging is best-effort and must **never** block or crash a real operation (a logging failure is swallowed *for logging only*, with a one-time internal notice — the one sanctioned "swallow", unlike domain errors [38](./38_ERROR_HANDLING.md)). The product functions fully even if logging is disabled.

## 15. Security

- **Local, redacted, no auto-egress** ([30](./30_SECURITY.md) §7): logs are as privacy-sensitive as the Timeline and are treated so. Security-relevant events (permission denials, integrity failures, sandbox violations) are logged at `WARN`/`ERROR` with enough context to investigate — but **without secrets** ([30](./30_SECURITY.md) §15). Log export is user-initiated/consented.

## 16. Performance

- Structured logging is cheap; hot sites are rate-limited/sampled; file I/O is buffered/async and off the hot path ([09](./09_PYTHON_BACKEND.md)/[31](./31_PERFORMANCE.md)). Logging never blocks the Çekirdek event loop or the UI thread.

## 17. Testing Strategy

- **No-secret test:** redaction scrubs keys/tokens; CI secret-scans logs.
- **No-stdout test (Çekirdek):** assert nothing but protocol reaches stdout ([09](./09_PYTHON_BACKEND.md) §20).
- **Correlation test:** a run's log lines carry the run/session/trace ids matching the Timeline.
- **Rotation/retention test:** logs bounded; disk not filled.
- **Non-blocking test:** logging failure doesn't fail a user op. See [35_TESTING](./35_TESTING.md).

## 18. Future Extensions

- A structured local diagnostics dashboard; opt-in, anonymized, consented crash reporting (strictly opt-in, categorized, [30](./30_SECURITY.md)); log query/filter tooling; per-subsystem tracing spans (OpenTelemetry-style, local exporter only).

## 19. Examples

```jsonc
// Çekirdek log line (stderr/file, NEVER stdout)
{"ts":"…","level":"INFO","tier":"core","module":"araclar.invoke",
 "msg":"tool invoked","sessionId":"s1","runId":"r1","traceId":"t1",
 "tool":"fs.write","path":"src/app.ts","bytes":1420}   // no secrets, ids for correlation
```

## 20. Anti-Patterns

- Logging to stdout in the Çekirdek (corrupts IPC).
- Logging secrets/auth headers/raw sensitive content.
- Auto-sending logs off-device (telemetry-by-default).
- Unbounded log growth / no rotation.
- Using logs as the product audit trail (that's the Timeline).
- Logging failures crashing/blocking real operations.

## 21. Things That Must Never Happen

1. Non-protocol output (a log line) is written to the Çekirdek's stdout.
2. A secret appears in any log.
3. Logs are transmitted off-device without explicit consent.
4. Logging fills the disk (must rotate/bound).
5. Logs are treated as/replace the durable Timeline audit.

## 22. Relationship With Other Subsystems

Distinct from but correlated with [26_TIMELINE](./26_TIMELINE.md); sinks the `detail` of [38_ERROR_HANDLING](./38_ERROR_HANDLING.md); routed via [10_IPC](./10_IPC.md)/[08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md); redaction with [34_API_KEYS](./34_API_KEYS.md)/[30_SECURITY](./30_SECURITY.md); stdout discipline from [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md); configured via [33_CONFIGURATION](./33_CONFIGURATION.md); bounded per [31_PERFORMANCE](./31_PERFORMANCE.md).

## 23. Migration Considerations

- Log format/levels evolve additively (PR-18); structured fields can be added freely. Redaction pattern sets are updated as new secret shapes appear (security-critical). Introducing any opt-in remote reporting is a major, consent-gated feature ([30](./30_SECURITY.md)) announced in [42_ROADMAP](./42_ROADMAP.md).
