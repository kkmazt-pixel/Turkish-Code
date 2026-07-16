# shell-app — turkish.code Desktop Shell (Tauri v2 host)

The Tauri v2 binary that hosts the Python Core on the desktop. It is a **thin
adapter** over [`shell-core`](../shell-core): every host responsibility — process
supervision, the Core Channel IPC, lifecycle, crash recovery, the permission
bridge, event forwarding — lives in `shell-core` and is fully tested there. This
crate only wires that runtime to Tauri: `#[tauri::command]` wrappers, an
`AppHandle`-backed event sink, and window-state tracking.

## Why it is excluded from the workspace

`shell-app` depends on the `tauri` crate, which needs webkit2gtk-4.1 and friends
to compile on Linux. Those are not installed yet, so the crate is listed under
`exclude` in the workspace `Cargo.toml` to keep the `shell-core` gates green
without them.

## Building it

1. Install the Tauri v2 Linux prerequisites (Arch/CachyOS):

   ```sh
   sudo pacman -S --needed webkit2gtk-4.1 librsvg libayatana-appindicator base-devel
   ```

   (`gtk3` and `libsoup3` are already present on this machine.)

2. Generate window/bundle icons (Tauri needs `icons/icon.png`):

   ```sh
   cargo tauri icon path/to/logo.png
   ```

3. Move `shell-app` from `exclude` to `members` in `shell/Cargo.toml`, then:

   ```sh
   cargo run -p shell-app        # dev run
   cargo tauri build             # release bundle
   ```

## What it does NOT contain

No React UI, no chat/settings screens, no business logic — those are other
phases. The `dist/` here is a placeholder frontend. No new IPC protocol is
introduced: the Core Channel from Phase 2 is reused verbatim.
