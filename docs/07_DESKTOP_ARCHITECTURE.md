# 07 — Desktop Architecture (Masaüstü Mimarisi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner tier:** Kabuk (Shell) + platform integration
> **Related:** [01_ARCHITECTURE](./01_ARCHITECTURE.md) · [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) · [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md) · [29_STORAGE](./29_STORAGE.md) · [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md)

---

## 1. Purpose

Defines turkish.code as a **cross-platform desktop application**: the OS-level concerns that sit above the tier decomposition ([01](./01_ARCHITECTURE.md)) — installation, packaging, the app-data layout on disk, window/OS integration, multi-window/multi-workspace, updates, single-instance behavior, GPU/hardware access, and platform-specific quirks. [08](./08_TAURI_ARCHITECTURE.md) covers the Tauri/Rust internals; this doc covers "it is a desktop app on Windows/macOS/Linux."

## 2. Scope

Supported platforms, packaging/distribution, on-disk data layout, OS integration (window, tray, notifications, file associations, deep links), updates, single/multi-instance, GPU access, and platform quirks. Out of scope: Tauri command internals ([08](./08_TAURI_ARCHITECTURE.md)), Python packaging internals ([09](./09_PYTHON_BACKEND.md)).

## 3. Goals

1. One codebase, three first-class OSes: **Windows 10+, macOS 12+, Linux (glibc; AppImage/deb/rpm)**.
2. A **small installer** that works **offline after install** (models fetched separately/on-demand, [22](./22_PROVIDER_INTEGRATIONS.md), [32](./32_OFFLINE_FIRST.md)).
3. Native OS integration that feels first-class (windowing, notifications, tray, file/URL association) without compromising the trust model ([01](./01_ARCHITECTURE.md)).
4. Deterministic, documented on-disk layout so support/recovery/migration is tractable.
5. GPU access for local inference where available, with clean CPU fallback (PR-7).

### Non-Goals
- Mobile/web targets ([43_NON_GOALS](./43_NON_GOALS.md)). It is a desktop app.

## 4. Platform Matrix

| Concern | Windows | macOS | Linux |
|---|---|---|---|
| WebView | WebView2 (Edge/Chromium) | WKWebView | WebKitGTK |
| Installer | `.msi` / `.exe` (NSIS) | `.dmg` / `.app` (signed+notarized) | `.AppImage`, `.deb`, `.rpm` |
| Secrets vault | Windows Credential Manager | Keychain | Secret Service (libsecret) / kwallet; fallback file-vault (encrypted) |
| GPU (local models) | CUDA (NVIDIA), DirectML fallback | Metal | CUDA (NVIDIA), Vulkan/CPU fallback |
| Autostart/tray | supported | supported | supported (varies by DE) |

WebView engine differences are the main source of frontend quirks; the Arayüz ([03](./03_UI_SYSTEM.md)) targets the lowest-common-denominator feature set and bundles polyfills/locale data where WebKitGTK lags (notably `Intl`/`tr` data — [03](./03_UI_SYSTEM.md) §16).

## 5. On-Disk Data Layout (Authoritative)

turkish.code uses OS-conventional directories. Canonical roots (resolved by the Kabuk and passed to the Çekirdek at spawn):

```
CONFIG_DIR   (per-OS app config)      →  settings.toml, providers, theme prefs   (doc 33)
DATA_DIR     (per-OS app data)        →  app.db (App DB), models cache, logs      (doc 29,39)
WORKSPACES   (under DATA_DIR/alanlar) →  <workspace-id>/  per workspace:
                                            workspace.db (index, memory, timeline)
                                            blobs/        (CAS snapshots, doc 27,29)
                                            journal/      (event journal, doc 26,28)
CACHE_DIR    (per-OS cache)           →  ephemeral, safe to delete
SECRETS                               →  OS keychain (NOT on disk in plaintext)   (doc 34)
```

Per-OS mapping (examples): Windows `%APPDATA%`/`%LOCALAPPDATA%`; macOS `~/Library/Application Support/turkish.code`; Linux XDG (`~/.config`, `~/.local/share`, `~/.cache`). Exact resolution and precedence: [33_CONFIGURATION](./33_CONFIGURATION.md). Storage formats: [29_STORAGE](./29_STORAGE.md).

**Invariant:** the user's *own project files* are never copied into DATA_DIR; the workspace DB/blobs/journal are *derived/metadata* stores that reference the project by path. Snapshots ([27](./27_SNAPSHOTS.md)) store content-addressed copies of *changed* files for undo, in the workspace blob store — never the whole project.

## 6. Packaging & Distribution

- Built by `scripts/package.sh` ([37](./37_REPOSITORY_STRUCTURE.md)). Tauri bundles the Arayüz assets + Kabuk binary; the Çekirdek is bundled as a **frozen Python runtime + deps** resource (see [09](./09_PYTHON_BACKEND.md) §packaging) so the user needs **no system Python**.
- **Models are not in the installer** (they can be many GB). First run offers to fetch the default local model(s) with checksum verification ([32](./32_OFFLINE_FIRST.md), [22](./22_PROVIDER_INTEGRATIONS.md)); an **offline installer variant** can pre-bundle a small default model for air-gapped installs.
- **Code signing:** Windows (Authenticode) and macOS (Developer ID + notarization) are required for a trustworthy install; Linux packages are signed where the format supports it. Unsigned dev builds are clearly marked.
- **Reproducible builds** are a goal (pinned toolchains, [33](./33_CONFIGURATION.md)) so an install can be audited (aligns with sovereignty, [30](./30_SECURITY.md)).

## 7. OS Integration

- **Windowing:** main window with the TTD chrome ([04](./04_TURKISH_DESIGN_LANGUAGE.md)); remembers size/position (trivial pref). Custom title bar optional per OS conventions.
- **Multi-window / multi-workspace:** each workspace opens in its own window; window ↔ workspace ↔ Çekirdek session scoping is defined in [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md) (decision: one Çekirdek process, per-workspace isolated sessions by default; optional one-process-per-workspace for heavy isolation).
- **Single instance:** a single-instance guard ensures a second launch focuses/opens in the existing app (or a new window) rather than spawning a competing set of processes fighting over the same DBs.
- **Notifications:** OS-native notifications for long-op completion, permission prompts when unfocused, and errors — routed through the Kabuk (which owns OS access). Content is minimal (no secrets/code in notification text).
- **Tray / background:** optional tray presence so a long agent run can continue with the window minimized; clearly indicates when the agent is active.
- **File associations & deep links:** optional `turkishcode://` deep link and "open folder as workspace"; deep links are validated and permission-checked by the Kabuk before acting (never auto-execute a link's payload — [30](./30_SECURITY.md)).

## 8. Updates

- **Opt-in auto-update** (Tauri updater) with signature verification; **no silent updates** and no update check without consent in privacy-strict mode ([30](./30_SECURITY.md), PR-16). Update checks are an *egress* event and are consent-gated like any other.
- Updates never touch user data/workspaces; migrations run on first launch of a new version ([33](./33_CONFIGURATION.md), [29](./29_STORAGE.md)).
- Fully-offline installs can update via a downloaded package (manual), preserving the air-gapped story.

## 9. Lifecycle (Desktop-Level)

Boot/shutdown of the *system* is in [01](./01_ARCHITECTURE.md) §9. Desktop-specific additions:
- **First run:** create app-data dirs, initialize App DB ([29](./29_STORAGE.md)), run onboarding (choose local model, set locale/theme, review privacy defaults).
- **Per launch:** single-instance check → restore windows/workspaces → resume recoverable sessions ([28](./28_CRASH_RECOVERY.md)).
- **Sleep/resume & network change:** the app handles OS sleep (pause long ops gracefully) and network transitions (offline↔online) by updating provider availability ([21](./21_PROVIDER_SYSTEM.md), [32](./32_OFFLINE_FIRST.md)) — never losing work.

## 10. GPU & Hardware Access

- Local inference and embeddings ([14](./14_EMBEDDINGS.md), [22](./22_PROVIDER_INTEGRATIONS.md)) use GPU when present (CUDA/Metal), managed inside the Çekirdek's runtimes. The Kabuk detects hardware at boot and reports capability to the Arayüz.
- Clean fallback ladder: GPU → smaller GPU model → CPU (slower) — a degradation ladder (PR-7, [31](./31_PERFORMANCE.md)).
- GPU memory pressure is monitored; the Çekirdek unloads idle models ([21](./21_PROVIDER_SYSTEM.md)).

## 11. Configuration

- Desktop prefs (window state, tray, autostart, update policy) live in app config ([33_CONFIGURATION](./33_CONFIGURATION.md)); privacy-relevant ones (update checks, telemetry) default to the most private setting ([30](./30_SECURITY.md)).

## 12. Dependencies

- Tauri 2.x runtime + the OS WebView (present on modern OSes; WebView2 auto-installed on Windows if missing, with consent). Bundled Çekirdek runtime ([09](./09_PYTHON_BACKEND.md)). No mandatory network service.

## 13. Edge Cases

- **Missing WebView2 (older Windows):** installer offers the bootstrapper (consent-gated egress) or a fixed-version bundle for offline installs.
- **Linux DE without a Secret Service:** fall back to an encrypted file-vault with a clear security notice ([34](./34_API_KEYS.md), [30](./30_SECURITY.md)).
- **Spaces/Unicode in install path or home dir** (note the dev root "Turkish Code" has a space): all path handling must be space/Unicode-safe ([37](./37_REPOSITORY_STRUCTURE.md) §11).
- **Two versions installed / stale sidecar:** version handshake ([01](./01_ARCHITECTURE.md) §14) prevents mismatched tiers.
- **Disk full during a session:** storage surfaces a typed error; no corruption due to journaling ([29](./29_STORAGE.md)).
- **No GPU / integrated GPU only:** CPU fallback; onboarding recommends an appropriately small model.

## 14. Failure Recovery

- Crash of any tier → [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md). Desktop-level: on relaunch, the single-instance + recovery flow restores windows/workspaces and offers session resume.
- Corrupt app-data (e.g., App DB) → the app boots into a safe diagnostic mode allowing repair/reset without touching user project files or workspace journals.

## 15. Security

- All OS capability is mediated by the Kabuk ([01](./01_ARCHITECTURE.md), [08](./08_TAURI_ARCHITECTURE.md)); the desktop layer adds signed installers/updates and OS-keychain secret storage. No open ports ([01](./01_ARCHITECTURE.md), [10](./10_IPC.md)). See [30_SECURITY](./30_SECURITY.md).

## 16. Performance

- Small binary, fast cold start (Tauri ≪ Electron), first paint independent of Çekirdek/model load ([03](./03_UI_SYSTEM.md), [31](./31_PERFORMANCE.md)). Model loading is lazy/background.

## 17. Testing Strategy

- Per-OS packaging smoke tests in CI (build installers on all three OSes).
- E2E on each OS's WebView (Playwright/Tauri driver) including the Turkish-locale suite.
- Install/upgrade/migration tests (fresh install, upgrade with data, air-gapped install). See [35_TESTING](./35_TESTING.md).

## 18. Future Extensions

- Portable/no-install mode; enterprise MSI policies; managed offline model bundles; a headless server install of just the Çekirdek for a LAN GPU box ([01](./01_ARCHITECTURE.md) §19, gated by [43_NON_GOALS](./43_NON_GOALS.md)).

## 19. Examples

- Air-gapped enterprise install: offline installer variant with a bundled small local model → first run works with zero network, privacy-strict defaults on.

## 20. Anti-Patterns

- Copying the user's entire project into app-data.
- Silent auto-update or update checks without consent.
- Bundling multi-GB models into the base installer.
- Assuming a system Python/Node is present.
- Unquoted path handling (breaks on spaces/Unicode).

## 21. Things That Must Never Happen

1. The installer or updater performs network egress without consent (PR-16).
2. Secrets are written to disk in plaintext (must use OS keychain/encrypted vault).
3. A second app instance corrupts shared DBs (single-instance guard required).
4. User project files are moved/deleted by install/update/migration.

## 22. Relationship With Other Subsystems

Hosts the tiers of [01](./01_ARCHITECTURE.md); the Kabuk internals are [08](./08_TAURI_ARCHITECTURE.md); the bundled brain is [09](./09_PYTHON_BACKEND.md). On-disk formats are [29_STORAGE](./29_STORAGE.md); config resolution is [33_CONFIGURATION](./33_CONFIGURATION.md); offline/model concerns are [32](./32_OFFLINE_FIRST.md)/[22](./22_PROVIDER_INTEGRATIONS.md); security posture is [30_SECURITY](./30_SECURITY.md).

## 23. Migration Considerations

- App-data layout is versioned; a layout change ships a first-launch migrator ([29](./29_STORAGE.md), [33](./33_CONFIGURATION.md)). Installer/updater changes preserve user data and never require re-fetching already-downloaded models. OS support additions/removals are announced in [42_ROADMAP](./42_ROADMAP.md).
