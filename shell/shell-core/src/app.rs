//! Desktop app — the composition root that wires the whole host (doc 07/08).
//!
//! [`DesktopApp`] assembles the pieces built across this phase into one runtime:
//! a supervised [`CoreLifecycle`], the [`ShellApi`] command surface over it, and
//! a [`CoreBridge`] that services the Core's inbound streams. It exposes the
//! lifecycle verbs the Tauri commands wrap — `bootstrap`, `restart`, `shutdown`
//! — plus the read/request surface, and it is the single object the Tauri binary
//! holds as managed state.
//!
//! `bootstrap` and `restart` drive the lifecycle and then (re-)attach the bridge
//! to the freshly minted Core streams, so notifications and permission requests
//! keep flowing across a restart. All methods take `&self` (state is behind
//! locks), so the app is shareable as `Arc<DesktopApp>`.

use std::sync::Arc;

use serde_json::Value;
use tokio::sync::Mutex;

use crate::bridge::CoreBridge;
use crate::commands::ShellApi;
use crate::core_process::CoreSpec;
use crate::errors::{ShellError, ShellResult};
use crate::events::EventSink;
use crate::lifecycle::{CoreLifecycle, LifecycleConfig};
use crate::message::Response;
use crate::permissions::PermissionResponder;
use crate::state::CoreStatus;

/// The composition root: lifecycle + command surface + Core bridge.
pub struct DesktopApp<R: PermissionResponder, S: EventSink> {
    lifecycle: Arc<Mutex<CoreLifecycle>>,
    api: ShellApi,
    bridge: CoreBridge<R, S>,
}

impl<R, S> DesktopApp<R, S>
where
    R: PermissionResponder + Send + Sync + 'static,
    S: EventSink + 'static,
{
    /// Assemble an app that launches the Core described by `spec`, decides
    /// permissions with `responder`, and re-emits Core events onto `sink`.
    #[must_use]
    pub fn new(spec: CoreSpec, config: LifecycleConfig, responder: R, sink: S) -> Self {
        let lifecycle = Arc::new(Mutex::new(CoreLifecycle::new(spec, config)));
        let api = ShellApi::from_shared(Arc::clone(&lifecycle));
        Self {
            lifecycle,
            api,
            bridge: CoreBridge::new(responder, sink),
        }
    }

    /// The command surface, for wiring Tauri `invoke` handlers.
    #[must_use]
    pub fn api(&self) -> ShellApi {
        self.api.clone()
    }

    /// Start the Core and attach the bridge to its inbound streams.
    ///
    /// # Errors
    /// Propagates a lifecycle start failure, or [`ShellError::Process`] if the
    /// started Core did not yield event streams to wire.
    pub async fn bootstrap(&self) -> ShellResult<()> {
        self.lifecycle.lock().await.start().await?;
        self.rewire().await
    }

    /// Restart the Core and re-attach the bridge to its fresh streams.
    ///
    /// # Errors
    /// Propagates a lifecycle restart failure, or [`ShellError::Process`] if the
    /// restarted Core did not yield event streams to wire.
    pub async fn restart(&self) -> ShellResult<()> {
        self.lifecycle.lock().await.restart().await?;
        self.rewire().await
    }

    /// Tear down the bridge workers and shut the Core down cleanly.
    ///
    /// # Errors
    /// Propagates a lifecycle shutdown failure.
    pub async fn shutdown(&self) -> ShellResult<()> {
        self.bridge.abort();
        self.lifecycle.lock().await.shutdown().await
    }

    /// The current Core status.
    pub async fn status(&self) -> CoreStatus {
        self.api.status().await
    }

    /// Heartbeat the Core and return its health snapshot.
    ///
    /// # Errors
    /// Propagates [`ShellApi::health`] failures.
    pub async fn health(&self) -> ShellResult<Value> {
        self.api.health().await
    }

    /// Forward a request to the Core and await its response.
    ///
    /// # Errors
    /// Propagates [`ShellApi::request`] failures.
    pub async fn request(&self, method: &str, params: Option<Value>) -> ShellResult<Response> {
        self.api.request(method, params).await
    }

    /// Take the current Core's streams and attach the bridge to them.
    async fn rewire(&self) -> ShellResult<()> {
        let (channel, events) = {
            let mut lifecycle = self.lifecycle.lock().await;
            let channel = lifecycle
                .channel()
                .ok_or_else(|| ShellError::Process("core is not running".to_owned()))?;
            let events = lifecycle.take_events().ok_or_else(|| {
                ShellError::Process("core event streams already taken".to_owned())
            })?;
            (channel, events)
        };
        self.bridge.attach(channel, events);
        Ok(())
    }
}

#[cfg(test)]
mod tests;
