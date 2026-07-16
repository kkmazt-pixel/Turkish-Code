//! Command surface — what the Tauri `invoke` handlers call (doc 08 §6).
//!
//! [`ShellApi`] is the shell's async command surface: bootstrap the Core, query
//! its status/health, forward a request to it, restart it, shut it down. The
//! Tauri binary's `#[tauri::command]` functions are **thin wrappers** over these
//! methods — they add no logic, so the substance stays here where it is directly
//! testable without a webview (doc 08 §6, PR-8).
//!
//! The Core lifecycle is shared behind an async lock so the surface is cheaply
//! cloneable and usable as Tauri managed state. Forwarded Core requests fetch a
//! channel handle and release the lock *before* the round trip, so independent
//! `invoke`s do not serialize behind each other.

use std::sync::Arc;

use serde_json::Value;
use tokio::sync::Mutex;

use crate::errors::{ShellError, ShellResult};
use crate::lifecycle::CoreLifecycle;
use crate::message::Response;
use crate::state::CoreStatus;

/// A cloneable, async command surface over a shared [`CoreLifecycle`].
#[derive(Clone)]
pub struct ShellApi {
    lifecycle: Arc<Mutex<CoreLifecycle>>,
}

impl ShellApi {
    /// Wrap `lifecycle` as a command surface.
    #[must_use]
    pub fn new(lifecycle: CoreLifecycle) -> Self {
        Self {
            lifecycle: Arc::new(Mutex::new(lifecycle)),
        }
    }

    /// Build a surface over an already-shared lifecycle (e.g. one a supervisor
    /// task also holds).
    #[must_use]
    pub fn from_shared(lifecycle: Arc<Mutex<CoreLifecycle>>) -> Self {
        Self { lifecycle }
    }

    /// The shared lifecycle handle, for wiring a supervisor alongside the surface.
    #[must_use]
    pub fn shared(&self) -> Arc<Mutex<CoreLifecycle>> {
        Arc::clone(&self.lifecycle)
    }

    /// Start the Core (`app.bootstrap`): spawn, wire, and health-gate it.
    ///
    /// # Errors
    /// Propagates [`CoreLifecycle::start`] failures.
    pub async fn bootstrap(&self) -> ShellResult<()> {
        self.lifecycle.lock().await.start().await
    }

    /// The current Core status, without touching the Core.
    pub async fn status(&self) -> CoreStatus {
        self.lifecycle.lock().await.status()
    }

    /// Heartbeat the Core and return its health snapshot (`app.health`).
    ///
    /// # Errors
    /// Propagates [`CoreLifecycle::health_check`] failures.
    pub async fn health(&self) -> ShellResult<Value> {
        let lifecycle = self.lifecycle.lock().await;
        lifecycle.health_check().await
    }

    /// Forward a request to the Core and await its correlated response.
    ///
    /// The lifecycle lock is released before the round trip, so concurrent
    /// `invoke`s run in parallel over the multiplexed channel.
    ///
    /// # Errors
    /// Returns [`ShellError::Process`] if the Core is not running, or the
    /// channel's error if the request fails.
    pub async fn request(&self, method: &str, params: Option<Value>) -> ShellResult<Response> {
        let channel = {
            let lifecycle = self.lifecycle.lock().await;
            lifecycle
                .channel()
                .ok_or_else(|| ShellError::Process("core is not running".to_owned()))?
        };
        channel.request(method, params).await
    }

    /// Restart the Core (`app.restart`), bounded by the restart budget.
    ///
    /// # Errors
    /// Propagates [`CoreLifecycle::restart`] failures.
    pub async fn restart(&self) -> ShellResult<()> {
        self.lifecycle.lock().await.restart().await
    }

    /// Shut the Core down cleanly (`app.shutdown`).
    ///
    /// # Errors
    /// Propagates [`CoreLifecycle::shutdown`] failures.
    pub async fn shutdown(&self) -> ShellResult<()> {
        self.lifecycle.lock().await.shutdown().await
    }
}

#[cfg(test)]
mod tests;
