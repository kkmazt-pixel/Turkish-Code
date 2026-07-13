# 34 — API Keys & Secrets (API Anahtarları)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 2.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek/config + provider adapters
> **Changed in v2.0** (per [52_ADR_LOG](./52_ADR_LOG.md) ADR-0010): **light key handling.** The earlier *heavy OS-keychain vault + injection-at-egress* apparatus is **rejected** (`PROJECT_ANALYSIS.md` L24). Keys are simply kept **outside source code** in configuration/environment and loaded to authenticate provider calls.
> **Related:** [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) · [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md) · [33_CONFIGURATION](./33_CONFIGURATION.md) · [39_LOGGING](./39_LOGGING.md) · [30_SECURITY](./30_SECURITY.md)

---

## 1. Purpose

Defines how turkish.code handles **API keys** for its cloud providers (Gemini, Groq, OpenRouter, NVIDIA NIM — [22](./22_PROVIDER_INTEGRATIONS.md)). The governing rule is deliberately **simple and light** ([52](./52_ADR_LOG.md) ADR-0010): **keys live outside source code** — in a local config file, a `.env`, or environment variables that are **git-ignored** — are loaded at startup, and used by the provider adapters to authenticate calls. Keys are **never committed** and **never logged** ([39](./39_LOGGING.md) redaction). turkish.code deliberately does **not** build a heavyweight OS-keychain vault with egress-injection brokering — that complexity was rejected as disproportionate for this product.

## 2. Scope

Where keys live (outside source), loading, the config reference, add/rotate/remove, and log redaction. Out of scope: provider selection ([21](./21_PROVIDER_SYSTEM.md)), per-provider auth quirks ([22](./22_PROVIDER_INTEGRATIONS.md)), routing ([45](./45_ROUTING_ORCHESTRATION.md)).

> **Note on the rest of this document:** sections below were written for the v1.0 heavy-keychain model and are **retained for reference but SUPERSEDED**. The light model (§1) is authoritative. Where an OS keychain *is* available and a user prefers it, it MAY be used as an optional backend, but it is **not required** and is not the default.

## 3. Goals

1. **Keys stay out of source code** and out of version control (the one hard rule that remains).
2. **Keys never appear in logs** ([39](./39_LOGGING.md) redaction).
3. **Simple to configure** — a config/env value per provider; no vault ceremony.
4. Optional (not required) OS-keychain backend for users who want it.

### (Superseded v1.0 goals — retained for reference)
1. **Secrets never leak**: not to the Çekirdek/Arayüz, not to DB/blob/journal/config/log/env (PR-1/PR-3, [30](./30_SECURITY.md) §12 #4).
2. **Minimal exposure**: a secret is decrypted/used only at the moment of an authorized, consented egress call, inside the trusted Kabuk, then discarded from memory.
3. **User control**: easy add/rotate/revoke; revocation is immediate and complete.
4. **Offline-safe**: local providers need no secret; a missing/locked keychain degrades to local-only, never insecure storage (PR-7).

### Non-Goals
- Not a password manager. Not secret *sharing*/sync. Not storage of the user's own project secrets (those live in the user's files; the app avoids indexing them, [25](./25_WORKSPACE_SYSTEM.md)).

## 4. Where Secrets Live

- **OS keychain** exclusively: Windows Credential Manager, macOS Keychain, Linux Secret Service (libsecret)/kwallet ([07](./07_DESKTOP_ARCHITECTURE.md) §4). Accessed **only** by the Kabuk `secrets/` module.
- Config ([33](./33_CONFIGURATION.md)) stores a **reference/handle** (e.g., `"keychain:nvidia-api-catalog"`), never the value. The reference tells the provider layer "there is a key by this handle"; only the Kabuk can resolve it.

## 5. The Injection-at-Egress Model (Core)

Secrets are **never** given to the Çekirdek. When a consented cloud call needs a key ([21](./21_PROVIDER_SYSTEM.md) §7):

```
Çekirdek builds the request (NO secret) → sends to Kabuk net broker (10/08) →
Kabuk: check net.egress consent (24/30) → resolve key from keychain (secrets/) →
       attach key to the outgoing HTTPS request → perform call → STRIP any secret
       from the response → stream response back to Çekirdek.
```

- The secret exists in plaintext **only** transiently in Kabuk memory during the call, then is dropped. It never crosses the Core Channel, never reaches the Arayüz, never persists.
- **Local providers** ([22](./22_PROVIDER_INTEGRATIONS.md)/llama.cpp/Ollama) need no secret and no egress → this whole path is skipped.

## 6. Secret Lifecycle

- **Add:** the user enters a key in a settings UI ([06](./06_COMPONENT_LIBRARY.md)); the Arayüz sends it via a dedicated Bridge command **straight to the Kabuk** which stores it in the keychain — the value is **not** echoed back, logged, or stored elsewhere. (The Arayüz holds it only for the instant of input; the field is treated as sensitive.)
- **Use:** injection-at-egress (§5), gated by consent.
- **Rotate:** replace in keychain; old value overwritten.
- **Revoke/Delete:** removed from keychain immediately; the referencing config handle is cleared; any provider needing it becomes unavailable (falls to local, [21](./21_PROVIDER_SYSTEM.md) §9).
- **List:** the UI shows *which* secrets exist (by handle/provider) and their status — **never the values** (masked).

## 7. Redaction & Leak Prevention

- **Logs ([39](./39_LOGGING.md)):** a redaction filter scrubs anything resembling a key; secrets are structurally absent (they never reach loggable code paths outside the Kabuk call site, which does not log them).
- **Timeline/memory ([26](./26_TIMELINE.md)/[11](./11_MEMORY_SYSTEM.md)):** redaction + secret scanning prevent persistence.
- **Errors ([38](./38_ERROR_HANDLING.md)):** error messages/responses never include the key (Kabuk strips before returning).
- **CI secret scanner** ([35](./35_TESTING.md)/[30](./30_SECURITY.md)) asserts no secret material in repo, DBs, blobs, journals, or logs.

## 8. No-Keychain Fallback

- If no OS Secret Service is available (some Linux setups) or the keychain is locked: the app **does not** store secrets in plaintext. Options, in order: (a) prompt the user to unlock/enable the keychain; (b) an **encrypted local vault** (a file encrypted with a key derived from an OS-protected mechanism or a user passphrase) with a clear security notice; (c) **degrade to local-only** (no cloud) — always preferring no-secret operation over insecure storage (PR-7, [30](./30_SECURITY.md)).

## 9. Architecture / Directory

```
apps/desktop/src-tauri/src/secrets/
  vault.rs        # keychain adapter (per-OS) + encrypted-file fallback
  inject.rs       # attach secret to a consented egress request; strip from response
  api.rs          # Bridge commands: add/rotate/revoke/list(masked) — Kabuk-only
```
(No secret code anywhere in the Çekirdek or Arayüz — enforced by review + tests.)

## 10. Configuration

- Config ([33](./33_CONFIGURATION.md)) holds only handles + provider enablement; the vault backend (keychain vs encrypted-file fallback) and consent requirements are configurable ([24](./24_PERMISSION_SYSTEM.md)/[30](./30_SECURITY.md)). Default: keychain, cloud disabled (no secrets needed).

## 11. Dependencies

- OS keychain libraries ([07](./07_DESKTOP_ARCHITECTURE.md)), [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) (egress + injection), [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) (consumer), [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md)/[30_SECURITY](./30_SECURITY.md) (consent), [33_CONFIGURATION](./33_CONFIGURATION.md) (handles).

## 12. Edge Cases

- **Keychain locked mid-session:** the pending cloud call fails with a typed "keychain locked" error; user unlocks or the run degrades to local — never falls back to plaintext.
- **Invalid/expired key:** provider call returns an auth error; surfaced clearly (masked), never logging the key; prompts rotation.
- **User pastes key into the wrong field / a chat message:** the input pipeline treats obvious secrets in chat as sensitive and warns/redacts (defense in depth) — but the *sanctioned* path is the settings vault.
- **Multiple keys for one provider (envs):** handles are namespaced; the active one is selected in config.
- **Backup/restore of app-data:** secrets are **not** in app-data (keychain), so a data backup never carries secrets — a feature, not a bug.
- **Uninstall:** offer to purge keychain entries.

## 13. Failure Recovery

- Secret operations are atomic against the keychain; a crash never leaves a secret in a half-persisted insecure state (it's either in the keychain or not). Recovery ([28](./28_CRASH_RECOVERY.md)) re-checks consent before any egress that needs a key.

## 14. Security

- This subsystem is the operational core of [30_SECURITY](./30_SECURITY.md) §7. Invariant recap: secrets **only** in keychain (or encrypted fallback), **only** touched by the Kabuk, injected transiently at consented egress, stripped from responses, redacted everywhere, never in Çekirdek/Arayüz/DB/log/config/env. Any deviation is a release blocker.

## 15. Performance

- Keychain access is fast and only on the (rare, consented) cloud path; local providers skip it entirely. Negligible impact ([31](./31_PERFORMANCE.md)).

## 16. Testing Strategy

- **Isolation tests (marquee):** assert no secret material is ever present in the Çekirdek process, the Arayüz, any DB/blob/journal, any log, or env — via instrumented fakes + scanners.
- **Injection tests:** a consented cloud call gets the key attached in the Kabuk and stripped from the response; the Çekirdek never sees it.
- **Fallback tests:** no keychain → encrypted vault or local-only, never plaintext.
- **Revoke tests:** deletion is immediate/complete; dependent provider becomes unavailable.
- **Redaction tests:** keys never appear in logs/errors. See [35_TESTING](./35_TESTING.md), [30_SECURITY](./30_SECURITY.md).

## 17. Future Extensions

- Hardware-backed keys (TPM/Secure Enclave); per-key scoping/expiry; enterprise-managed secret provisioning; OAuth-style flows for providers that support them (tokens handled with the same discipline).

## 18. Examples

- User enables NVIDIA API Catalog: pastes the key in settings → Kabuk stores it as `keychain:nvidia-api-catalog`; config records the handle + `providers.cloud.nvidia = enabled`. A later `Maksimum` run with egress consent triggers a cloud call: the Çekirdek builds the request, the Kabuk attaches the key from the keychain, performs the HTTPS call, strips the key, and streams back — the key never left the Kabuk.

## 19. Anti-Patterns

- Storing a key in config/DB/log/env "temporarily."
- Passing a key to the Çekirdek so it can call the API directly.
- Returning/echoing the key to the Arayüz.
- Plaintext fallback when no keychain exists.
- Logging request headers that contain the key.

## 20. Things That Must Never Happen

1. A secret is stored anywhere but the OS keychain (or encrypted fallback) — never plaintext.
2. A secret reaches the Çekirdek or the Arayüz (persisted or in memory beyond input).
3. A secret appears in a DB, blob, journal, log, error, or env var.
4. A cloud call sends a key without prior egress consent.
5. Revocation leaves a usable residual copy anywhere.

## 21. Relationship With Other Subsystems

Sealed/injected by [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md); consumed (indirectly) by cloud providers in [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md)/[22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md); gated by [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md); referenced (by handle) in [33_CONFIGURATION](./33_CONFIGURATION.md); redaction with [26_TIMELINE](./26_TIMELINE.md)/[11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md)/[39_LOGGING](./39_LOGGING.md); the operational heart of [30_SECURITY](./30_SECURITY.md) §7.

## 22. Migration Considerations

- The vault backend can evolve (keychain → hardware-backed) behind the `secrets/` interface (PR-8) without exposing secrets. Config handle format is versioned ([33](./33_CONFIGURATION.md)). Migrating secret stores must never write a plaintext intermediate. Adding OAuth/token flows extends, not replaces, the discipline.
