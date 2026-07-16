//! turkish.code Desktop Shell — Tauri v2 host binary.
//!
//! A **thin adapter** over [`shell_core`]: it constructs a [`DesktopApp`], holds
//! it as Tauri managed state, and exposes it to the WebView through
//! `#[tauri::command]` wrappers that add no logic. Core notifications are
//! re-emitted to the WebView via an [`EventSink`] backed by [`AppHandle::emit`],
//! and window focus is tracked into a [`WindowState`]. All host logic — process
//! supervision, IPC, lifecycle, permissions — lives in `shell-core`; this file
//! only bridges it to the OS/WebView. No new IPC protocol; the Core Channel is
//! reused verbatim.

// Hide the extra console window on Windows in release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::{Arc, Mutex};

use serde_json::Value;
use shell_core::{
    CoreSpec, CoreStatus, DesktopApp, EventSink, LifecycleConfig, PermissionMode, PolicyResponder,
    Response, WindowState,
};
use tauri::{AppHandle, Emitter, Manager, State, WindowEvent};

/// The concrete app type held as managed state.
type Desktop = Arc<DesktopApp<PolicyResponder, AppHandleSink>>;
/// Window state shared between the window-event hook and its query command.
type WindowHandle = Arc<Mutex<WindowState>>;

/// An [`EventSink`] that re-emits Core notifications as Tauri events (doc 08 §6).
struct AppHandleSink {
    handle: AppHandle,
}

impl EventSink for AppHandleSink {
    fn emit(&self, name: &str, payload: &Value) {
        // A closed WebView is not fatal to the host; drop emit errors.
        let _ = self.handle.emit(name, payload.clone());
    }
}

const fn status_name(status: CoreStatus) -> &'static str {
    match status {
        CoreStatus::Stopped => "stopped",
        CoreStatus::Starting => "starting",
        CoreStatus::Running => "running",
        CoreStatus::Restarting => "restarting",
        CoreStatus::Crashed => "crashed",
    }
}

#[tauri::command]
async fn core_bootstrap(app: State<'_, Desktop>) -> Result<(), String> {
    app.bootstrap().await.map_err(|err| err.to_string())
}

#[tauri::command]
async fn core_shutdown(app: State<'_, Desktop>) -> Result<(), String> {
    app.shutdown().await.map_err(|err| err.to_string())
}

#[tauri::command]
async fn core_restart(app: State<'_, Desktop>) -> Result<(), String> {
    app.restart().await.map_err(|err| err.to_string())
}

#[tauri::command]
async fn core_status(app: State<'_, Desktop>) -> Result<String, String> {
    Ok(status_name(app.status().await).to_owned())
}

#[tauri::command]
async fn core_health(app: State<'_, Desktop>) -> Result<Value, String> {
    app.health().await.map_err(|err| err.to_string())
}

#[tauri::command]
async fn core_request(
    app: State<'_, Desktop>,
    method: String,
    params: Option<Value>,
) -> Result<Value, String> {
    match app
        .request(&method, params)
        .await
        .map_err(|err| err.to_string())?
    {
        Response::Success(result) => Ok(result),
        Response::Error(err) => Err(err.message),
    }
}

#[tauri::command]
fn window_state(window: State<'_, WindowHandle>) -> Result<Value, String> {
    let state = window
        .lock()
        .map_err(|_| "window state poisoned".to_owned())?;
    Ok(serde_json::json!({
        "visible": state.is_visible(),
        "focused": state.is_focused(),
    }))
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // Build the host over the real Python Core (`python -m turkish_code`).
            let sink = AppHandleSink {
                handle: app.handle().clone(),
            };
            let spec = CoreSpec::new("python3").arg("-m").arg("turkish_code");
            let desktop: Desktop = Arc::new(DesktopApp::new(
                spec,
                LifecycleConfig::default(),
                PolicyResponder::new(PermissionMode::Ask),
                sink,
            ));
            app.manage(desktop);
            app.manage::<WindowHandle>(Arc::new(Mutex::new(WindowState::default())));
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::Focused(focused) = event {
                if let Some(state) = window.try_state::<WindowHandle>() {
                    if let Ok(mut window_state) = state.lock() {
                        window_state.set_focused(*focused);
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            core_bootstrap,
            core_shutdown,
            core_restart,
            core_status,
            core_health,
            core_request,
            window_state,
        ])
        .run(tauri::generate_context!())
        .expect("error while running the turkish.code desktop shell");
}
