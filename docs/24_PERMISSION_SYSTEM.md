# 24 — Permission System (İzinler)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Kabuk `permission/` (enforcement) + policy defined here
> **Related:** [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) · [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) · [30_SECURITY](./30_SECURITY.md) · [27_SNAPSHOTS](./27_SNAPSHOTS.md) · [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md)

---

## 1. Purpose

Defines **İzinler**, the capability-based permission model that keeps the user in control of everything the agent does — the structural basis of Pillar P5 ("trustworthy by construction") and a load-bearing part of P1 (privacy). It specifies the capability taxonomy, permission **modes**, the consent flow, grant scoping/persistence, and how enforcement is made *unavoidable* by routing every side effect through the Kabuk ([08](./08_TAURI_ARCHITECTURE.md)). The permission engine is the single most safety-critical policy component in the system.

## 2. Scope

The capability model, permission modes, the request/decision/consent flow, grant persistence and scoping, egress/telemetry consent, and the fail-safe defaults. The *enforcement mechanics* (where the code runs) live in [08](./08_TAURI_ARCHITECTURE.md) §11; this doc owns the *policy*. Out of scope: tool schemas ([20](./20_TOOL_SYSTEM.md)), snapshots ([27](./27_SNAPSHOTS.md)), plugin grants specifics ([23](./23_PLUGIN_SYSTEM.md), which build on this).

## 3. Goals

1. **User is always in control**: no sensitive or irreversible action without an appropriate authorization (P5).
2. **Enforcement is structural, not optional** (PR-1/PR-2): every side effect passes the engine because every side effect is a brokered tool ([20](./20_TOOL_SYSTEM.md)/[08](./08_TAURI_ARCHITECTURE.md)).
3. **Least privilege** everywhere (PR-3): default-deny; grant the minimum, scoped as tightly as possible.
4. **Consent for egress** is explicit, per-category, revocable, and logged (PR-16, [30](./30_SECURITY.md)).
5. **Usable, not naggy**: modes and remembered grants make safety low-friction without becoming rubber-stamping.

### Non-Goals
- Not a sandbox implementation (that's OS/tier boundaries [08](./08_TAURI_ARCHITECTURE.md)/[09](./09_PYTHON_BACKEND.md)). Not authentication of a remote user (single-user desktop app).

## 4. Capability Taxonomy (Yetki)

Every gated action maps to exactly one capability. Core set:

| Capability | Guards | Reversible? | Default |
|---|---|---|---|
| `fs.read` | reading user files | n/a (read) | allow in-workspace |
| `fs.write` | creating/editing/deleting user files | yes (snapshot [27]) | **ask** |
| `shell.exec` | running commands | partial | **ask** (per command) |
| `net.egress` | any network send (incl. cloud providers, updates, telemetry) | n/a | **deny** (consent to enable) |
| `open.external` | opening URLs/files in the OS | n/a | ask |
| `secret.use` | using a stored secret for an authorized call | n/a | tied to net.egress consent |
| `workspace.switch` | operating on a different workspace | n/a | ask |
| `plugin.capability.*` | plugin-requested capabilities ([23](./23_PLUGIN_SYSTEM.md)) | varies | **deny** until granted |

- Capabilities are **fine-grained and target-scoped**: a grant is `capability × target` (e.g., `fs.write` on `src/**`, `shell.exec` for `npm test`, `net.egress` to `api.nvidia.com`). A blanket grant is the exception, always explicit.

## 5. Permission Modes (İzin Modu)

A session runs in one mode, chosen by the user (default configurable):

| Mode | Turkish | Behavior |
|---|---|---|
| **Plan** | Planla | **Read-only.** The agent may read/retrieve/reason and *propose* actions, but **no** mutating/exec/egress action runs. Safest; ideal for review. |
| **Ask** | Sor (default) | Sensitive actions (`fs.write`, `shell.exec`, `net.egress`, …) prompt the user each time (with remember-options). Reads in-scope are allowed. |
| **Auto** | Otomatik | Pre-granted within an explicit scope (e.g., "auto-approve `fs.write` in this workspace for this session"); still snapshotted + audited; egress still requires standing consent. |

- **Mode never overrides a hard deny**: even in `Auto`, `net.egress` requires standing egress consent (privacy is not auto-grantable by a convenience mode). Destructive/irreversible actions may still confirm even in `Auto` (see §7).
- Effort mode ([17](./17_EFFORT_MODES.md)) is orthogonal: more effort ≠ more permission.

## 6. Request → Decision → Consent Flow

```
Tool.invoke (Çekirdek, 20) ──▶ Kabuk permission engine (08 §11)
   evaluate(mode, standing grants, capability, target):
     • matches a standing grant/scope       → ALLOW
     • Plan mode & sensitive               → DENY (typed)
     • Ask mode & sensitive & no grant     → RAISE permission.request → user (06 §6.5)
     • Auto mode & in granted scope        → ALLOW
     • else                                → DENY
   on ALLOW + mutate → snapshot BEFORE effect (27); append timeline event (26)
   on user decision (permission.respond):
     • "Bir kez izin ver" (once)           → allow this call only
     • "Her zaman (bu kapsamda)" (always)  → persist a scoped standing grant
     • "Reddet" (deny)                     → deny; model adapts (15)
     • "Planla" (switch to plan)           → downgrade session to read-only
```

- The prompt (`IzinIstemi`, [06](./06_COMPONENT_LIBRARY.md) §6.5) shows **exactly** what will happen: capability, precise target (path/command/host), and why. Destructive scopes use `mercan` and require deliberate confirmation ([04](./04_TURKISH_DESIGN_LANGUAGE.md)).
- **Fail-safe:** if no UI can answer (window closed) or on any ambiguity/error, the decision is **deny** ([08](./08_TAURI_ARCHITECTURE.md) §15).

## 7. Destructive & Irreversible Actions

- Actions that are **irreversible or high-impact** (deleting many files, `rm -rf`-like commands, force-push, mass overwrite, egress of large content) are flagged and get **extra friction**: an explicit confirmation even in `Auto`, with a clear description. Where possible they're made reversible first (snapshot [27]); truly irreversible ones (e.g., network sends) can't be undone, so they get the strongest consent gate (PR-4/PR-16).

## 8. Grant Scoping & Persistence

- **Scopes:** `once` (this call), `session` (until session ends), `workspace` (persisted for this project), `global` (rare, explicit). Each grant is `capability × target × scope`.
- **Persistence:** standing grants are stored in the **App/Workspace DB** ([29](./29_STORAGE.md)) as **non-secret policy** (the *permission* to use a secret is here; the *secret itself* is in the keychain [34]).
- **Review & revoke:** the user can view and revoke all standing grants at any time (a settings panel); revocation is immediate. Grants are auditable ([26](./26_TIMELINE.md)).

## 9. Egress & Telemetry Consent (Privacy Core)

- **`net.egress` is default-deny.** Enabling any cloud provider ([21](./21_PROVIDER_SYSTEM.md)/[22](./22_PROVIDER_INTEGRATIONS.md)), update check ([07](./07_DESKTOP_ARCHITECTURE.md)), model download, or telemetry requires an explicit, **per-category**, revocable consent — each is a distinct grant, not a blanket "go online" (PR-16, [30](./30_SECURITY.md)/[32](./32_OFFLINE_FIRST.md)).
- **Telemetry is off by default**; if ever offered, it is opt-in, categorized, and inspectable. No egress is silent; each is logged.

## 10. Architecture / Data Flow

- **Policy** (this doc) is evaluated by the **engine in the Kabuk** (`permission/`, [08](./08_TAURI_ARCHITECTURE.md) §11). The Çekirdek holds only an opaque `permissionCtx` token in run `meta` ([10](./10_IPC.md)) referencing the session's mode/grants; it cannot self-authorize. Enforcement location = the broker choke point ⇒ unavoidable (PR-1/PR-2).

```
Çekirdek (has permissionCtx, cannot decide) → tool.invoke → Kabuk engine (decides) →
   allow → snapshot(27)+broker exec(08)+timeline(26) | ask → user | deny → typed
```

## 11. Configuration

- Default mode, default-deny/allow per capability, destructive-action list, and consent categories are configurable ([33](./33_CONFIGURATION.md)) with **privacy-strongest defaults** ([30](./30_SECURITY.md)). Enterprises can lock policies (e.g., force Plan/Ask, forbid egress).

## 12. Dependencies

- [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) (enforcement), [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) (what's gated), [27_SNAPSHOTS](./27_SNAPSHOTS.md) (reversibility), [26_TIMELINE](./26_TIMELINE.md) (audit), [29_STORAGE](./29_STORAGE.md) (grant store), [34_API_KEYS](./34_API_KEYS.md) (secret use), [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md) (plugin grants), [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md) (prompt UI).

## 13. Edge Cases

- **Prompt while unfocused:** OS notification ([07](./07_DESKTOP_ARCHITECTURE.md)); unanswered → deny (fail-safe).
- **Agent tries to widen its own scope:** impossible — the Çekirdek can't self-authorize; only the user grants ([18](./18_AGENT_SYSTEM.md) sub-agents get *subsets*).
- **Rapid repeated prompts (prompt fatigue):** remembered scoped grants + `Auto` mode reduce fatigue *without* becoming blanket allow; batching related requests into one clear prompt where safe.
- **Revoked grant mid-run:** next matching action re-prompts/denies; in-flight ops respect the revocation at the next check.
- **Ambiguous target (glob/symlink):** canonicalize; deny on traversal escape ([20](./20_TOOL_SYSTEM.md) §9).
- **Plan mode but user asks agent to edit:** the agent proposes a diff ([06](./06_COMPONENT_LIBRARY.md) §6.4) the user can apply after switching mode — never a silent write.
- **Standing grant + policy lock conflict (enterprise):** policy lock wins.

## 14. Failure Recovery

- Grants are journaled ([29](./29_STORAGE.md)); a crash never loses or silently loosens them. On recovery, the session's mode/grants are restored ([28](./28_CRASH_RECOVERY.md)). If the grant store is unreadable, the engine defaults to the most restrictive mode (fail-safe).

## 15. Security

- This subsystem **is** much of [30_SECURITY](./30_SECURITY.md). Invariants: default-deny; least privilege; egress consent; fail-safe deny; no self-authorization by the Çekirdek/agents/plugins; every decision + effect audited. It is small and in the trusted tier so it can be fully reviewed. Prompt-injection can only cause the agent to *request*; the engine + user decide.

## 16. Performance

- Evaluation is O(grants) with indexed lookups — negligible latency on the tool path. Prompts are the only user-latency and are minimized via remembered scoped grants and `Auto`. Metrics in [31_PERFORMANCE](./31_PERFORMANCE.md).

## 17. Testing Strategy

- **Enforcement completeness:** fuzz every tool/capability — none executes a sensitive effect without an allow decision.
- **Mode tests:** Plan blocks all mutation/exec/egress; Ask prompts; Auto respects scope but never auto-grants egress.
- **Fail-safe tests:** no UI / error / unreadable store → deny / most-restrictive.
- **Scope/revocation tests:** grants apply only within scope; revocation is immediate.
- **No-self-auth tests:** the Çekirdek/agents/plugins cannot widen their own permissions.
- **Destructive-action friction tests.** See [35_TESTING](./35_TESTING.md), [30_SECURITY](./30_SECURITY.md).

## 18. Future Extensions

- Policy templates ("Sıkı/strict", "Dengeli", "Geliştirici") one-click profiles; enterprise MDM-managed policies; time-boxed grants; per-command shell allowlists learned over time; richer target predicates.

## 19. Examples

- Ask mode: agent wants to run `npm test` → prompt "Komut çalıştırılsın mı? `npm test` (bu çalışma alanında)" → user picks "Her zaman (bu kapsamda)" → future `npm test` runs auto; `rm -rf build` still prompts (different target, destructive friction).

## 20. Anti-Patterns

- A side effect path that doesn't consult the engine (PR-2 violation).
- Blanket "allow all" grants by default.
- `Auto` mode auto-granting egress.
- Letting the model/agent/plugin self-authorize.
- Prompts that don't show the precise target/why (rubber-stamping).
- Silent egress or telemetry.

## 21. Things That Must Never Happen

1. A sensitive/irreversible action runs without an allow decision.
2. Egress/telemetry happens without explicit, revocable consent.
3. The Çekirdek, an agent, or a plugin authorizes its own action.
4. A failure/ambiguity results in allow (must fail-safe to deny).
5. A destructive action runs without appropriate friction/confirmation.

## 22. Relationship With Other Subsystems

Enforced by [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md); gates [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) (and thus [15](./15_REASONING_ENGINE.md)/[18](./18_AGENT_SYSTEM.md)/[23](./23_PLUGIN_SYSTEM.md)); pairs with [27_SNAPSHOTS](./27_SNAPSHOTS.md) for reversibility and [26_TIMELINE](./26_TIMELINE.md) for audit; governs egress with [21](./21_PROVIDER_SYSTEM.md)/[34](./34_API_KEYS.md)/[32](./32_OFFLINE_FIRST.md); is the heart of [30_SECURITY](./30_SECURITY.md); prompts via [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md).

## 23. Migration Considerations

- The capability taxonomy is versioned; adding a capability is additive but defaults to **deny** (safe). Renaming/merging capabilities is a migration that must re-map existing grants conservatively (never silently broaden). New destructive-action classifications ship deny/friction-on. Enterprise policy schema is forward-compatible.
