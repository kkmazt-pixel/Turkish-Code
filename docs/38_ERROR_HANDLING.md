# 38 — Error Handling (Hata Yönetimi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** cross-cutting (Çekirdek `hata/`, Kabuk error types, Arayüz error surface)
> **Related:** [10_IPC](./10_IPC.md) · [39_LOGGING](./39_LOGGING.md) · [36_CODING_STANDARDS](./36_CODING_STANDARDS.md) · [04_TURKISH_DESIGN_LANGUAGE](./04_TURKISH_DESIGN_LANGUAGE.md) · [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md)

---

## 1. Purpose

Defines the **unified error model** for turkish.code: a typed error taxonomy shared across tiers, how errors propagate over IPC, how they map to user-facing Turkish messages, and the discipline that makes failures *values* (categorized, retryable-or-not, with remedies) rather than silent exceptions (PR-10). Good error handling is what makes the product feel trustworthy under stress — every failure should tell the user (or the agent) what happened and what to do.

## 2. Scope

The error taxonomy, error value shape, propagation across the two IPC links, user-facing message rules (Turkish, calm, actionable), retry/degradation semantics, and the boundary between recoverable errors and crashes. Out of scope: logging ([39](./39_LOGGING.md)), crash recovery ([28](./28_CRASH_RECOVERY.md)), the IPC envelope details ([10](./10_IPC.md)).

## 3. Goals

1. **Typed, never silent** (PR-10): every failure is a typed value with category, retryability, and remedy.
2. **Actionable & calm for users**: Turkish, blame-free, specific about the next step ([04](./04_TURKISH_DESIGN_LANGUAGE.md) §12).
3. **Machine-actionable for the agent**: the reasoning loop can decide retry/degrade/ask from the error's fields ([15](./15_REASONING_ENGINE.md)).
4. **Uniform across tiers**: one taxonomy, mapped cleanly over IPC ([10](./10_IPC.md)).
5. **Fail-safe**: on ambiguity, prefer the safe outcome (deny/stop) over guessing ([24](./24_PERMISSION_SYSTEM.md)/[30](./30_SECURITY.md)).

### Non-Goals
- Not logging/telemetry ([39](./39_LOGGING.md)). Not stack-trace display to end users (those go to logs).

## 4. Error Taxonomy (Categories)

Every error has a `kind` from a shared, versioned enum (defined in `ipc-schema` + Çekirdek `hata/`):

| Category | Examples | Typically retryable? |
|---|---|---|
| `Validation` | bad tool args, malformed input ([20](./20_TOOL_SYSTEM.md)) | no (fix input) |
| `Permission` | denied capability ([24](./24_PERMISSION_SYSTEM.md)) | no (adapt/ask) |
| `NotFound` | missing file/entity/model | no |
| `Conflict` | edit conflict, version skew ([27](./27_SNAPSHOTS.md)/[10](./10_IPC.md)) | sometimes |
| `Provider` | model/provider failure, context-window exceeded ([21](./21_PROVIDER_SYSTEM.md)) | often (failover/retry) |
| `Egress` | offline/no-consent/network ([30](./30_SECURITY.md)/[32](./32_OFFLINE_FIRST.md)) | no while offline |
| `Resource` | disk full, OOM, GPU OOM ([29](./29_STORAGE.md)/[31](./31_PERFORMANCE.md)) | sometimes (degrade) |
| `Budget` | effort budget exhausted ([17](./17_EFFORT_MODES.md)) | no (raise effort) |
| `Timeout` | deadline exceeded ([10](./10_IPC.md)) | sometimes |
| `Cancelled` | user cancelled ([10](./10_IPC.md)) | n/a |
| `Corruption` | corrupt index/store (rebuildable) ([13](./13_RAG_SYSTEM.md)/[29](./29_STORAGE.md)) | via rebuild |
| `Internal` | unexpected bug | no (report) |
| `Security` | integrity/signature/sandbox violation ([30](./30_SECURITY.md)) | no (block) |

## 5. Error Value Shape

Errors are structured values (not bare strings/exceptions):

```
AppError {
  kind: <category>            // §4
  code: string               // stable machine code, e.g. "tool.args.invalid"
  messageKey: string         // i18n key → Turkish user message (03/04)
  detail?: string            // developer detail (logged, not shown raw to user)
  retryable: bool
  remedyKey?: string         // i18n key → "what to do" (e.g., "Derin modu deneyin")
  cause?: AppError           // chained cause
  context?: {...}            // redacted structured context (no secrets, 30/34)
}
```

- **`messageKey`/`remedyKey`** resolve to localized strings (tr default) — errors are **not** raw English strings ([04](./04_TURKISH_DESIGN_LANGUAGE.md) §12, PR-12).
- **`retryable`/`kind`/`remedyKey`** are what the agent and UI act on programmatically (PR-10/PR-11).
- **`detail`/`context`** are for logs ([39](./39_LOGGING.md)) — **redacted of secrets** ([34](./34_API_KEYS.md)/[30](./30_SECURITY.md)); never shown raw to users.

## 6. Propagation Across Tiers

- **Çekirdek → Kabuk (Core Channel):** an `AppError` becomes a JSON-RPC `error` object; `error.data = {kind, code, retryable, remedy, …}` ([10](./10_IPC.md) §14).
- **Kabuk → Arayüz (Bridge):** re-emitted as a typed error result or a `run.failed`/`notification` event with the localized message + remedy.
- **Rust ↔ Python type parity:** the taxonomy is codegen'd/shared via `ipc-schema` so `kind`/`code` match on both sides (Contract Gate, [35](./35_TESTING.md)).
- **Cause chaining** is preserved across tiers (for logs) but flattened to a single user message at the surface.

## 7. Handling Discipline

- **At the point of failure:** construct a precise typed `AppError` (right `kind`, stable `code`, `messageKey`, `retryable`, `remedyKey`). Never `except: pass`, never swallow ([36](./36_CODING_STANDARDS.md)).
- **Propagation:** let it bubble as a typed value; add context (chain a cause) at boundaries; don't stringify-and-rethrow (loses type).
- **At the agent ([15](./15_REASONING_ENGINE.md)):** inspect `kind`/`retryable`: `Provider`→failover/retry ([21](./21_PROVIDER_SYSTEM.md)); `Permission`→adapt/ask; `Budget`→finalize+suggest higher effort; `Resource`→degrade ([31](./31_PERFORMANCE.md)); `Validation`→re-plan/re-prompt. The agent never presents a wrong confident answer in place of surfacing an error.
- **At the UI ([03](./03_UI_SYSTEM.md)/[06](./06_COMPONENT_LIBRARY.md)):** show the localized message + remedy in a calm `Banner`/inline state; offer the remedy action where possible (e.g., "Derin modu dene", "Çevrimiçi ol", "Yeniden dene"). Raw stack traces go to logs, never the user.

## 8. User-Facing Message Rules (Turkish, Calm, Actionable)

- **Language:** Turkish by default, natural and blame-free ("İşlem tamamlanamadı" not "HATA: exception in module X"). Correct casing (PR-12).
- **Specific + actionable:** say what happened *and* the next step ("Model yanıtı zaman aşımına uğradı. Yeniden deneyebilir veya daha hızlı bir mod seçebilirsiniz.").
- **No jargon/leaks:** no stack traces, no internal identifiers, no secrets, no scary red walls of text ([04](./04_TURKISH_DESIGN_LANGUAGE.md) voice; `mercan` used sparingly for genuine danger).
- **Consistent:** message/remedy come from i18n keys, so wording is centralized and reviewable.

## 9. Recoverable Error vs Crash

- **Recoverable errors** (§4) are the norm: typed, surfaced, handled — the session continues or fails gracefully with a clear state.
- **Crashes** (unexpected `Internal`, process death) are the exception: caught at the top boundary, converted to a typed `Internal` error where possible, checkpointed, and handed to crash recovery ([28](./28_CRASH_RECOVERY.md)). The Arayüz error boundary ([03](./03_UI_SYSTEM.md) §17) catches render crashes → safe reload (no data loss).
- The dividing line: an *expected* failure mode is a typed recoverable error; an *unexpected* one is a crash routed to recovery. Both are handled; neither is silent.

## 10. Directory Structure

```
core/turkish_code/hata/     # AppError, taxonomy, constructors, chaining
apps/desktop/src-tauri/…    # Rust error types mirroring the taxonomy
apps/desktop/src/…          # Arayüz error surface + i18n error strings
packages/ipc-schema/…       # shared error kind/code enum (source of truth)
```

## 11. Configuration

- Verbosity of `detail`/`context` in logs is config-driven ([39](./39_LOGGING.md)); user message tone/formality follows locale settings ([04](./04_TURKISH_DESIGN_LANGUAGE.md)/[33](./33_CONFIGURATION.md)). Retry/backoff policies per category are configurable ([21](./21_PROVIDER_SYSTEM.md)/[10](./10_IPC.md)).

## 12. Dependencies

- [10_IPC](./10_IPC.md) (error propagation), [39_LOGGING](./39_LOGGING.md) (detail sink), [03_UI_SYSTEM](./03_UI_SYSTEM.md)/[06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md)/[04_TURKISH_DESIGN_LANGUAGE](./04_TURKISH_DESIGN_LANGUAGE.md) (surface + i18n), [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) (agent handling), [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md) (crash path), [30_SECURITY](./30_SECURITY.md)/[34_API_KEYS](./34_API_KEYS.md) (redaction).

## 13. Edge Cases

- **Error while handling an error:** a fallback minimal `Internal` error + log; never infinite error loops.
- **Non-localized error (missing key):** fall back to a generic localized message + log the missing key (never show the raw English/dev string to the user).
- **Secret in error context:** redaction pass strips it before logging/surfacing ([34](./34_API_KEYS.md)).
- **Partial success** (some sub-agents failed, [18](./18_AGENT_SYSTEM.md)): report partial completion with per-item errors, not a blanket failure.
- **Errors during streaming:** emit `run.failed` with the typed error; the UI transitions the stream to an error state gracefully ([03](./03_UI_SYSTEM.md) §8).
- **Cancelled vs failed:** distinct kinds; cancellation is not an error state ([10](./10_IPC.md)).

## 14. Failure Recovery

- Recoverable errors keep the session alive (retry/degrade/ask). Unexpected crashes route to [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md) with checkpoints. The system's default under any doubt is the **safe** path (stop/deny/finalize), never a risky guess ([30](./30_SECURITY.md)).

## 15. Security

- Errors **never leak secrets** or sensitive internals to the user/logs (redaction, [34](./34_API_KEYS.md)/[30](./30_SECURITY.md)). `Security`-kind errors fail closed and are logged as security events ([39](./39_LOGGING.md)). Error messages don't reveal exploitable internals (no path/stack leaks to the UI).

## 16. Performance

- Error construction is cheap; the hot path is the success path. Retries use bounded backoff ([21](./21_PROVIDER_SYSTEM.md)) — no error storms (PR-14). See [31_PERFORMANCE](./31_PERFORMANCE.md).

## 17. Testing Strategy

- **Every typed error has a test** that provokes it and asserts `kind`/`retryable`/`remedy` ([35](./35_TESTING.md) §8).
- **Agent-handling tests:** injected `Provider`/`Permission`/`Budget` errors lead to failover/adapt/finalize, not wrong answers ([15](./15_REASONING_ENGINE.md)).
- **Localization tests:** messages resolve to Turkish; missing-key fallback works; no raw dev strings to users.
- **Redaction tests:** no secrets in error detail/context. See [35_TESTING](./35_TESTING.md).

## 18. Future Extensions

- Rich in-app remedy actions (one-click "switch model", "go online", "rebuild index"); user-friendly error report export (local); error analytics (local-only) to spot common failure modes; a shared remedy library.

## 19. Examples

```jsonc
// Core Channel error → localized surface
{ "error": { "code": -32050, "message": "Yanıt zaman aşımı",
    "data": { "kind":"Timeout", "code":"provider.timeout",
              "retryable":true, "remedy":"caba.hizli_dene" } } }
// UI shows: "Model yanıtı zaman aşımına uğradı. Yeniden deneyin veya daha hızlı bir mod seçin."
```

## 20. Anti-Patterns

- `except: pass` / bare `catch` / swallowing.
- Returning `null`/`None` to signal failure.
- Raw stack traces / English dev strings shown to users.
- Stringify-and-rethrow (loses type/cause).
- Leaking secrets/internals in messages.
- Infinite retry / error storms.
- Presenting a fabricated answer instead of surfacing an error.

## 21. Things That Must Never Happen

1. A failure is silently swallowed (must be a typed value).
2. A raw stack trace or secret reaches the end user.
3. An error message is un-localized English shown as the primary user text.
4. The agent emits a confident wrong answer instead of an error when it failed.
5. Error handling fails open on a security/permission ambiguity.

## 22. Relationship With Other Subsystems

Propagated over [10_IPC](./10_IPC.md); detail sinks to [39_LOGGING](./39_LOGGING.md); surfaced via [03_UI_SYSTEM](./03_UI_SYSTEM.md)/[06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md)/[04_TURKISH_DESIGN_LANGUAGE](./04_TURKISH_DESIGN_LANGUAGE.md); acted on by [15_REASONING_ENGINE](./15_REASONING_ENGINE.md)/[21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md); crash path to [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md); redaction with [34_API_KEYS](./34_API_KEYS.md)/[30_SECURITY](./30_SECURITY.md); coded per [36_CODING_STANDARDS](./36_CODING_STANDARDS.md).

## 23. Migration Considerations

- The error `kind`/`code` enum is versioned in `ipc-schema`; adding kinds/codes is additive (PR-18); consumers handle unknown kinds as a generic recoverable error. Renaming a code is a migration (stable codes matter for the agent + analytics). Message keys evolve additively with i18n.
