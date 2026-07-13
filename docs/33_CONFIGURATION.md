# 33 — Configuration (Yapılandırma)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `yapilandirma/` + Kabuk (app config) + `packages` (toolchain)
> **Related:** [07_DESKTOP_ARCHITECTURE](./07_DESKTOP_ARCHITECTURE.md) · [29_STORAGE](./29_STORAGE.md) · [34_API_KEYS](./34_API_KEYS.md) · [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) · [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md)

---

## 1. Purpose

Defines the **configuration system**: the layered resolution order, the config schema and where it lives on disk, the runtime-vs-build config split, defaults (with privacy-strongest bias), validation, and hot-reload. Configuration is the single place that answers "what setting applies here?" for every subsystem, so it must be deterministic, layered, and legible (PR-9/PR-11). It explicitly excludes secrets (those are [34_API_KEYS](./34_API_KEYS.md)).

## 2. Scope

Config layers and precedence, schema/format, on-disk locations, defaults, validation, hot-reload, and the toolchain/version matrix. Out of scope: secrets ([34](./34_API_KEYS.md)), what each setting *does* (its subsystem doc), storage internals ([29](./29_STORAGE.md)).

## 3. Goals

1. **Layered, deterministic resolution**: a clear precedence so any effective value is explainable (PR-9).
2. **Privacy-strongest defaults**: offline, egress off, telemetry off, strict-safe — out of the box ([30](./30_SECURITY.md)/[32](./32_OFFLINE_FIRST.md)).
3. **Legible & typed**: human-editable TOML + a validated schema; machine-readable ([40](./40_DOCUMENTATION_RULES.md), PR-11).
4. **Scoped**: global vs workspace vs session overrides ([25](./25_WORKSPACE_SYSTEM.md)/[17](./17_EFFORT_MODES.md)).
5. **Safe to change**: validation + hot-reload where safe; migration for schema changes.

### Non-Goals
- Not secret storage ([34](./34_API_KEYS.md)). Not feature logic. Not per-user cloud sync.

## 4. Config Layers & Precedence

Effective config = later layers override earlier (each layer is partial):

```
1. BUILT-IN DEFAULTS        (shipped; privacy-strongest)             ← lowest precedence
2. APP CONFIG               (CONFIG_DIR/settings.toml — user global)
3. WORKSPACE CONFIG         (DATA_DIR/alanlar/<id>/config.toml — per project, doc 25)
4. SESSION / RUNTIME        (effort mode, per-message overrides, doc 17)
5. ENTERPRISE POLICY LOCK   (may TIGHTEN only; cannot secretly loosen)  ← highest, constrained
```

- Precedence is fixed and documented; the app can **explain an effective value** ("this came from workspace config"). Enterprise policy is special: it can only make things *more* restrictive (e.g., force offline), never silently *less* ([30](./30_SECURITY.md)/[24](./24_PERMISSION_SYSTEM.md)).

## 5. Runtime vs Build Config

- **Runtime config** (this doc's focus): user-facing app behavior — locale/theme/density ([03](./03_UI_SYSTEM.md)/[04](./04_TURKISH_DESIGN_LANGUAGE.md)), providers/model pins ([21](./21_PROVIDER_SYSTEM.md)), effort defaults ([17](./17_EFFORT_MODES.md)), permission defaults ([24](./24_PERMISSION_SYSTEM.md)), retention/perf knobs ([26](./26_TIMELINE.md)/[27](./27_SNAPSHOTS.md)/[31](./31_PERFORMANCE.md)), paths ([07](./07_DESKTOP_ARCHITECTURE.md)). Lives in the OS app-data dirs, **not** in the repo.
- **Build/toolchain config** (in the repo): tool versions, lockfiles, CI ([37](./37_REPOSITORY_STRUCTURE.md)). The **authoritative version matrix** (Node/pnpm, Rust/Tauri, Python/uv, SQLite/sqlite-vec, model defaults) is maintained here as a reference table and pinned in lockfiles.
- **Seed defaults** ship as templates under `apps/desktop/src-tauri/resources/defaults` and are copied on first run ([07](./07_DESKTOP_ARCHITECTURE.md)).

## 6. Format & Schema

- **Format:** TOML for human-editable files (comments, clarity); the App DB holds a few dynamic settings (provider registry, grants — [29](./29_STORAGE.md)/[24](./24_PERMISSION_SYSTEM.md)). Trivial view prefs go through a Kabuk pref store ([03](./03_UI_SYSTEM.md) §14).
- **Schema:** a typed, versioned schema (validated on load; the source of truth for valid keys/types/ranges, aligned with `ipc-schema` discipline). Unknown keys warn (forward-compat); invalid values are rejected with a clear message and fall back to the default for that key (fail-safe, never crash on a bad config).
- **`schema_version`** in each config file drives migrations (§10).

## 7. On-Disk Locations

Resolved by the Kabuk and passed to the Çekirdek ([07](./07_DESKTOP_ARCHITECTURE.md) §5):

```
CONFIG_DIR/settings.toml                       # app/global (layer 2)
DATA_DIR/alanlar/<id>/config.toml              # workspace (layer 3)
CACHE_DIR/...                                   # ephemeral, safe to delete
<repo>/… (build only)                          # toolchain/lockfiles (layer: build)
```
Per-OS `CONFIG_DIR`/`DATA_DIR` mapping is in [07_DESKTOP_ARCHITECTURE](./07_DESKTOP_ARCHITECTURE.md) §5.

## 8. Defaults (Privacy-Strongest)

Canonical shipped defaults:
- `locale = "tr"`, `theme = "gece"` (system-aware), density `rahat` ([03](./03_UI_SYSTEM.md)/[04](./04_TURKISH_DESIGN_LANGUAGE.md)).
- `effort = "dengeli"` ([17](./17_EFFORT_MODES.md)).
- `permission.mode = "ask"`, `net.egress = deny`, `telemetry = off`, `updates = consented` ([24](./24_PERMISSION_SYSTEM.md)/[30](./30_SECURITY.md)).
- `providers`: local-only enabled; cloud disabled ([21](./21_PROVIDER_SYSTEM.md)/[32](./32_OFFLINE_FIRST.md)).
- Durability: journal/snapshot fsync on; retention windows sane ([29](./29_STORAGE.md)/[26](./26_TIMELINE.md)).

The product is fully functional under defaults with no configuration and no network ([32](./32_OFFLINE_FIRST.md)).

## 9. Access Pattern

- All subsystems read config through the `yapilandirma/` loader (the DI-provided `Config` object, [09](./09_PYTHON_BACKEND.md) §7) — **no subsystem reads files/env directly** (PR-2/PR-9, one path). This centralizes precedence, validation, and hot-reload. Config is **passed explicitly** to subsystems, not read from a global.

## 10. Migration

- Config schemas are versioned; on app upgrade, a **forward-only migrator** upgrades each config file's `schema_version` (adds new keys with safe defaults, renames with mapping). Aligned with storage migrations ([29](./29_STORAGE.md) §10) and run at first launch of a new version ([07](./07_DESKTOP_ARCHITECTURE.md) §8). A config that can't be migrated falls back to defaults for the affected section with a clear notice (never blocks startup on a config issue).

## 11. Hot-Reload

- Safe-to-change settings (theme, density, effort defaults, retention windows, some provider prefs) **hot-reload** on file change / UI change without restart. Settings that require a restart (e.g., process-isolation mode [25], certain paths) are marked and applied on next launch with a clear indication. Editing a file externally triggers validation + reload.

## 12. Dependencies

- [07_DESKTOP_ARCHITECTURE](./07_DESKTOP_ARCHITECTURE.md) (paths), [29_STORAGE](./29_STORAGE.md) (DB-backed dynamic settings + migration alignment), [34_API_KEYS](./34_API_KEYS.md) (secrets — referenced by config but stored separately), and every subsystem (consumers).

## 13. Edge Cases

- **Corrupt/invalid config file:** per-key fallback to default + surfaced warning; never crash.
- **Conflicting layers:** precedence (§4) resolves deterministically; the app can explain the winner.
- **Enterprise lock vs user setting:** lock wins (tighten-only).
- **Path with spaces/Unicode** (dev root "Turkish Code"): handled safely ([37](./37_REPOSITORY_STRUCTURE.md)).
- **Setting references a missing provider/model:** validated at load; falls back with a notice ([21](./21_PROVIDER_SYSTEM.md)).
- **Downgrade (older app, newer config):** unknown keys ignored (warn); if incompatible, section defaults used.
- **Secret referenced in config:** config stores only a **reference/handle** to a keychain secret, never the secret ([34](./34_API_KEYS.md)).

## 14. Failure Recovery

- Config never blocks the app: worst case is running on validated defaults with a warning. A reset-to-defaults path exists (deleting a config file regenerates it from the seed). Migrations are atomic per file ([29](./29_STORAGE.md)).

## 15. Security

- **No secrets in config** — only references ([34](./34_API_KEYS.md)/[30](./30_SECURITY.md)). Defaults are privacy-strongest (§8). Enterprise policy can lock security settings tighter. Config files are user-owned local files (no egress). See [30_SECURITY](./30_SECURITY.md).

## 16. Performance

- Config is loaded once at boot (+ hot-reload on change), cached in the `Config` object; reads are O(1) in-memory. Negligible runtime cost. See [31_PERFORMANCE](./31_PERFORMANCE.md).

## 17. Testing Strategy

- **Precedence tests:** each layer overrides correctly; effective value explainable.
- **Validation tests:** invalid values fall back per-key; unknown keys warn; no crash.
- **Migration tests:** forward migrations add/rename keys with safe defaults; unmigratable → section defaults.
- **Default-privacy test:** shipped defaults are offline/egress-off/telemetry-off (a security gate, [30](./30_SECURITY.md)).
- **No-secret test:** config never contains secret material ([34](./34_API_KEYS.md)). See [35_TESTING](./35_TESTING.md).

## 18. Future Extensions

- In-app settings UI generated from the schema (legible/typed pays off); config profiles ("Sıkı/Dengeli/Geliştirici"); import/export of config; org-managed policy distribution; per-provider advanced config panels.

## 19. Examples

```toml
# CONFIG_DIR/settings.toml (layer 2)
locale = "tr"
theme = "gece"
[effort]
default = "dengeli"
[permission]
mode = "ask"
[net]
egress = "deny"          # cloud/telemetry/updates all require explicit consent
[providers.local]
chat = "nim:local-default"
embed = "nemo-retriever:local"   # secret? none (local). cloud provider would ref a keychain handle
```

## 20. Anti-Patterns

- Reading files/env directly in a subsystem instead of via the loader.
- Storing secrets in config.
- Non-deterministic precedence / unexplainable effective values.
- Crashing on a bad config value (must fall back).
- Privacy-loose defaults.
- Silent enterprise loosening of security settings.

## 21. Things That Must Never Happen

1. A secret is stored in a config file (references only).
2. Shipped defaults enable egress/telemetry/cloud without consent.
3. A subsystem bypasses the config loader (breaks precedence/validation).
4. An invalid config crashes the app instead of falling back.
5. Enterprise policy secretly loosens a security setting (tighten-only).

## 22. Relationship With Other Subsystems

Feeds every subsystem's tunables; paths from [07_DESKTOP_ARCHITECTURE](./07_DESKTOP_ARCHITECTURE.md); dynamic settings + migration alignment with [29_STORAGE](./29_STORAGE.md); references (not stores) secrets in [34_API_KEYS](./34_API_KEYS.md); scoped by [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md); defaults bias set by [30_SECURITY](./30_SECURITY.md)/[32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md); effort/runtime layer from [17_EFFORT_MODES](./17_EFFORT_MODES.md).

## 23. Migration Considerations

- Config schema is versioned; forward-only migrations at launch (§10) aligned with [29](./29_STORAGE.md). Adding keys is additive with safe defaults (PR-18); renaming maps old→new; removing keeps a deprecation window. The toolchain version matrix (§5) evolves in the repo and is announced in [42_ROADMAP](./42_ROADMAP.md).
