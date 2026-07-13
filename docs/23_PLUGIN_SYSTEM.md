# 23 — Plugin System (Eklentiler)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `eklenti/` (host) + `plugins/` (content) + Kabuk (sandbox enforcement)
> **Related:** [19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md) · [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) · [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) · [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md) · [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) · [30_SECURITY](./30_SECURITY.md)

---

## 1. Purpose

Defines **Eklentiler** (Plugins): the distributable extension mechanism by which third parties (and the community) add capabilities to turkish.code — bundling any of skills ([19](./19_SKILLS_SYSTEM.md)), tools ([20](./20_TOOL_SYSTEM.md)), providers ([21](./21_PROVIDER_SYSTEM.md)), agents ([18](./18_AGENT_SYSTEM.md)), or UI panels ([03](./03_UI_SYSTEM.md)). A plugin is the *container/format/lifecycle*; the capabilities inside are governed by their own subsystem docs. The defining challenge is **safe extensibility**: letting untrusted code extend the app without ever weakening the pillars — especially privacy, permission, and offline guarantees.

## 2. Scope

The plugin manifest/format, capability contributions, the install/load/enable lifecycle, the sandbox + capability-grant model, versioning/compat, and the registry. Out of scope: the internals of each contributed capability (their subsystem docs), the permission engine itself ([24](./24_PERMISSION_SYSTEM.md)).

## 3. Goals

1. **Extend everything** (skills/tools/providers/agents/UI) through one coherent, declarative package (PR-11, PR-13).
2. **Untrusted by default**: a plugin gets **zero** capability until the user grants it; nothing a plugin does can bypass permissions, egress consent, or snapshots (PR-1/PR-2/PR-3).
3. **Offline-installable & offline-runnable** (PR-6): plugins can be installed from local files; a plugin must not make a core feature network-dependent.
4. **Sandboxed & auditable**: plugin activity is confined and fully recorded ([26](./26_TIMELINE.md)).
5. **Stable, versioned contribution APIs** so plugins survive app updates (PR-18).

### Non-Goals
- Not a way to inject privileged native code into the trusted Kabuk tier (plugins never run in the Kabuk). Not a bypass of any pillar. Not first-party skills (those live in `skills/`, [19](./19_SKILLS_SYSTEM.md)).

## 4. Plugin Package & Manifest

`plugins/<name>/` (or an installable archive). Manifest `plugin.toml`:

```toml
[plugin]
id = "org.example.turkce-lint"
name = "Türkçe Lint"
version = "1.2.0"
min_app_version = "1.0.0"
authors = ["..."]
license = "..."

[contributes]           # what it adds (all optional)
skills   = ["skills/turkce-lint"]        # doc 19
tools    = ["tools/lint_check"]          # doc 20 (ToolDefs)
providers= []                             # doc 21
agents   = ["agents/lint_reviewer"]      # doc 18
ui       = ["panels/lint_panel"]         # doc 03 (sandboxed panel)

[capabilities-requested] # MUST be declared; user must grant (24/30)
fs = "read"              # e.g., read-only fs; "write" would be a stronger ask
net = "none"             # "none" ⇒ offline-safe; "egress" ⇒ consent required
shell = "none"

[runtime]
kind = "python"          # sandboxed Çekirdek-side extension
entry = "main.py"
```

- **`capabilities-requested` is the security contract**: a plugin must declare exactly what it needs; the user reviews and grants at install ([24](./24_PERMISSION_SYSTEM.md)). Undeclared capability is impossible to use.
- Contributions reference standard subsystem artifacts (a plugin tool is a normal `ToolDef` [20]; a plugin skill is a normal `SKILL.md` [19]) — the plugin system doesn't invent parallel formats.

## 5. Contribution Types

| Contributes | Governed by | Sandbox/limits |
|---|---|---|
| Skills | [19](./19_SKILLS_SYSTEM.md) | inert knowledge; scripts run only via granted tools |
| Tools | [20](./20_TOOL_SYSTEM.md) | full tool lifecycle: schema-validated, permission-gated, snapshot/timeline |
| Providers | [21](./21_PROVIDER_SYSTEM.md) | egress (if any) via Kabuk broker + consent; local providers run in worker |
| Agents | [18](./18_AGENT_SYSTEM.md) | least-privilege tool grants; bounded; validated `AgentDef` |
| UI panels | [03](./03_UI_SYSTEM.md)/[06](./06_COMPONENT_LIBRARY.md) | sandboxed panel; token-only styling; no raw fs/net; contrast/a11y gates |

Every contribution flows through its subsystem's existing gates — the plugin adds *content*, never a new *path* around the guarantees.

## 6. Sandbox & Capability-Grant Model (Critical)

- **Where plugins run:** plugin logic runs **inside the Çekirdek's sandbox** (a restricted worker), **never** in the trusted Kabuk. It therefore has the same brokered-effect boundary as the rest of the Çekirdek ([09](./09_PYTHON_BACKEND.md) §9): any user-world effect must go through a granted tool → Kabuk permission engine.
- **Capability grants:** at install/enable, the user grants (or denies) each requested capability. Grants are stored ([24](./24_PERMISSION_SYSTEM.md)) and **intersected** with runtime permissions: a plugin tool call must satisfy *both* the plugin's grant *and* the session permission mode. Least privilege by construction (PR-3).
- **Resource confinement:** CPU/memory/time limits on plugin workers; plugin egress (if granted) still goes through the single Kabuk `net.rs` path with consent ([08](./08_TAURI_ARCHITECTURE.md)/[30](./30_SECURITY.md)).
- **UI sandbox:** plugin panels render in a constrained context — no direct Bridge access beyond a narrow, permissioned plugin-UI API; token-only styling ([04](./04_TURKISH_DESIGN_LANGUAGE.md)); sanitized content ([03](./03_UI_SYSTEM.md) §13).
- **Result:** a malicious plugin can, at worst, do what the user explicitly granted — and even then only through the permissioned, snapshotted, audited paths. It can never open a hidden socket, read arbitrary files, or bypass a snapshot.

## 7. Lifecycle

```
DISCOVER (plugins/ + installed dir)
  → VALIDATE manifest + contributions (schema, signatures) — reject invalid (fail-safe)
  → INSTALL: show requested capabilities → USER GRANTS/DENIES (24)
  → ENABLE: register contributions into the respective registries (18/19/20/21)
  → RUN: contributions used like first-party, under grants + permissions
  → UPDATE: re-review capabilities if they changed (re-consent on escalation)
  → DISABLE/UNINSTALL: unregister; revoke grants; remove (auditable)
```

- Capability **escalation** on update (asking for more than before) requires fresh user consent — a plugin can't silently grow its powers (PR-16).

## 8. Registry & Isolation

- A plugin registry ([09](./09_PYTHON_BACKEND.md) DI) tracks installed plugins, their grants, health, and contributions. Contributions are namespaced by plugin id to avoid collisions (`org.example.turkce-lint/lint_check`).
- Plugins are isolated from each other (no shared mutable state; separate workers) so one misbehaving plugin can't corrupt another.

## 9. Configuration

- Enabled plugins, per-plugin capability grants, per-workspace plugin sets, and resource limits live in config ([33](./33_CONFIGURATION.md)); grants recorded in the permission store ([24](./24_PERMISSION_SYSTEM.md)). Default: no third-party plugins enabled.

## 10. Dependencies

- [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) (grants/enforcement), [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) (broker/egress/sandbox enforcement), [18](./18_AGENT_SYSTEM.md)/[19](./19_SKILLS_SYSTEM.md)/[20](./20_TOOL_SYSTEM.md)/[21](./21_PROVIDER_SYSTEM.md) (contribution registries), [30_SECURITY](./30_SECURITY.md), [26_TIMELINE](./26_TIMELINE.md) (audit).

## 11. Edge Cases

- **Invalid/incompatible plugin** (`min_app_version` mismatch, bad manifest): rejected at validate; clear error; no partial load.
- **Capability over-ask:** user can deny specific capabilities; the plugin must degrade or refuse to enable (its choice), but never gets ungranted capability.
- **Plugin crashes/hangs:** isolated worker killed; plugin auto-disabled after repeated failures; app unaffected (fail-safe).
- **Plugin tries undeclared capability:** blocked by the intersection model (§6); logged as a security event ([30](./30_SECURITY.md)).
- **Malicious UI panel:** sandbox + CSP + sanitization contain it; can't reach fs/net/secrets.
- **Offline install:** supported from local archive; a plugin that *needs* egress must declare it and still can't break offline core features (PR-6).
- **Two plugins contribute the same tool/skill name:** namespacing prevents collision; the engine disambiguates.

## 12. Failure Recovery

- Disabling/uninstalling a plugin cleanly unregisters contributions and revokes grants. Plugin failures never corrupt user data (all effects were snapshot/timeline-tracked [27]/[26]). Registry rebuild is idempotent.

## 13. Security (Central Concern)

- **Trust model:** third-party plugins are **untrusted**. Everything in §6 exists to make untrusted extension safe. Recap of invariants: never in the Kabuk; zero ambient capability; all effects via granted+permissioned tools; egress only via consented Kabuk path; snapshotted + audited; resource-limited; UI-sandboxed.
- **Distribution integrity:** plugins can be **signed**; the app verifies signatures and shows publisher/verification state. A curated registry (future) adds review. Users are warned about unsigned/unverified plugins ([30](./30_SECURITY.md)).
- **Supply chain:** plugin dependencies are declared; the app doesn't auto-execute install-time scripts with privilege. See [30_SECURITY](./30_SECURITY.md).

## 14. Performance

- Plugin workers are resource-capped and lazily activated; a slow plugin can't degrade the core (isolation + limits). Plugin skills/tools obey the same budgets ([17](./17_EFFORT_MODES.md)) as first-party. Metrics in [31_PERFORMANCE](./31_PERFORMANCE.md).

## 15. Testing Strategy

- **Sandbox-escape tests:** a plugin cannot perform an undeclared/unpermissioned effect, open a hidden socket, read out-of-scope files, or access secrets.
- **Grant-intersection tests:** effects require both plugin grant AND session permission.
- **Escalation-consent tests:** updated capabilities require re-consent.
- **Isolation tests:** one plugin's crash/hang doesn't affect others or the core.
- **Offline tests:** offline install; core stays functional. See [35_TESTING](./35_TESTING.md), [30_SECURITY](./30_SECURITY.md).

## 16. Future Extensions

- A curated, signed plugin registry/marketplace; capability "profiles" for one-click safe grants; plugin sandboxing via OS-level isolation (WASM/subprocess jails) for stronger guarantees; revenue/licensing hooks; org-managed allowlists for enterprises.

## 17. Examples

- "Türkçe Lint" plugin contributes a `lint_check` tool (read-only fs), a skill that knows when to run it, and a results panel. On install the user grants only `fs:read`, `net:none`. It can analyze code and report issues — but literally cannot write files, reach the network, or see secrets.

## 18. Anti-Patterns

- Running plugin code in the trusted Kabuk tier.
- Granting a plugin ambient capability "to make it work."
- A plugin capability path that bypasses permission/snapshot/timeline.
- Silent capability escalation on update.
- A plugin that makes a core feature require the network.
- Unsandboxed plugin UI with raw Bridge/fs/net access.

## 19. Things That Must Never Happen

1. Plugin code executes in the Kabuk / gains ambient OS capability.
2. A plugin performs an undeclared or unpermissioned effect (fs/shell/egress).
3. A plugin reads secrets or opens a hidden network socket.
4. A plugin escalates its granted capabilities without fresh user consent.
5. A plugin makes a core feature network-dependent (breaks P1/offline).

## 20. Relationship With Other Subsystems

Packages contributions governed by [18](./18_AGENT_SYSTEM.md)/[19](./19_SKILLS_SYSTEM.md)/[20](./20_TOOL_SYSTEM.md)/[21](./21_PROVIDER_SYSTEM.md)/[03](./03_UI_SYSTEM.md); grants + enforcement via [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md); sandbox/egress via [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md); audited by [26_TIMELINE](./26_TIMELINE.md); constrained by [30_SECURITY](./30_SECURITY.md) and [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md); budgeted by [17_EFFORT_MODES](./17_EFFORT_MODES.md).

## 21. Migration Considerations

- Contribution APIs and the manifest are versioned (`min_app_version`); additive changes preferred (PR-18). A plugin incompatible with a new app version is disabled with a clear message, not silently broken. Capability-model changes trigger a re-consent flow. Signed-plugin verification is forward-compatible.
