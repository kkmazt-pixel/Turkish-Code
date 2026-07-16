//! Lifecycle — supervising one Core process through its whole life (doc 09 §11).
//!
//! [`CoreLifecycle`] composes the lower primitives — [`CoreSpec`]/[`CoreProcess`]
//! for the OS boundary, [`CoreChannel`] for IPC and heartbeats, [`ShellState`]
//! for observable status — into the supervision policy: **start** (spawn, wire,
//! gate on a health check), **shutdown** (graceful, then stop), **health check**
//! (heartbeat the live Core), **crash detection** (has the process exited?), and
//! **restart** (respawn from the retained spec, bounded by a restart budget).
//!
//! It holds no business logic: it decides *when* to spawn, heartbeat, or restart
//! the Core, never *what* the Core computes. The retained [`CoreSpec`] is the
//! single source of truth for how a replacement process is launched.

use std::sync::Arc;
use std::time::Duration;

use serde_json::Value;

use crate::core_process::{CoreProcess, CoreSpec};
use crate::errors::{ShellError, ShellResult};
use crate::ipc::{CoreChannel, CoreEvents};
use crate::state::{CoreStatus, ShellState};

/// Tuning for the supervision policy.
#[derive(Debug, Clone)]
pub struct LifecycleConfig {
    /// How long a startup or health-check heartbeat may take before failing.
    pub heartbeat_timeout: Duration,
    /// Maximum number of restarts before the supervisor gives up.
    pub max_restarts: u32,
}

impl Default for LifecycleConfig {
    fn default() -> Self {
        Self {
            heartbeat_timeout: Duration::from_secs(5),
            max_restarts: 3,
        }
    }
}

/// One live Core process together with its channel and inbound event side.
///
/// The channel is shared (`Arc`) so command handlers can issue concurrent Core
/// requests without holding the lifecycle lock across the round trip.
struct Running {
    process: CoreProcess,
    channel: Arc<CoreChannel>,
    events: Option<CoreEvents>,
}

/// Supervises a single Core process across start, health, crash, and restart.
pub struct CoreLifecycle {
    spec: CoreSpec,
    config: LifecycleConfig,
    state: ShellState,
    current: Option<Running>,
}

impl CoreLifecycle {
    /// Create a supervisor for the Core described by `spec` (not yet started).
    #[must_use]
    pub fn new(spec: CoreSpec, config: LifecycleConfig) -> Self {
        Self {
            spec,
            config,
            state: ShellState::new(),
            current: None,
        }
    }

    /// The current observable status of the Core process.
    #[must_use]
    pub fn status(&self) -> CoreStatus {
        self.state.status()
    }

    /// How many times the Core has been restarted so far.
    #[must_use]
    pub fn restart_count(&self) -> u32 {
        self.state.restart_count()
    }

    /// A shared handle to the live Core Channel, if the Core is running.
    ///
    /// Returns a fresh `Arc` clone each call, so a caller never holds a channel
    /// that outlives a restart if it re-fetches before each use.
    #[must_use]
    pub fn channel(&self) -> Option<Arc<CoreChannel>> {
        self.current
            .as_ref()
            .map(|running| Arc::clone(&running.channel))
    }

    /// The inbound event side (notifications, Core→shell requests) of the live
    /// Core, if it is still held here. Consumed once by [`take_events`](Self::take_events).
    pub fn events(&mut self) -> Option<&mut CoreEvents> {
        self.current
            .as_mut()
            .and_then(|running| running.events.as_mut())
    }

    /// Take ownership of the live Core's inbound event side, leaving none.
    ///
    /// The composition moves these receivers into background tasks (the
    /// permission bridge and event forwarder). A fresh set is produced on each
    /// start/restart, so the wiring re-takes them after every respawn.
    pub fn take_events(&mut self) -> Option<CoreEvents> {
        self.current
            .as_mut()
            .and_then(|running| running.events.take())
    }

    /// Start the Core: spawn it, wire the channel, and gate on a health check.
    ///
    /// The Core is only reported `Running` once it answers a heartbeat, so a
    /// successful `start` means the channel is live — not merely that a process
    /// was spawned.
    ///
    /// # Errors
    /// Returns [`ShellError::Process`] if a Core is already running, or the spawn
    /// or startup health check fails (the spawned process is cleaned up on a
    /// failed gate).
    pub async fn start(&mut self) -> ShellResult<()> {
        if self.current.is_some() {
            return Err(ShellError::Process("core is already running".to_owned()));
        }
        self.state.set_status(CoreStatus::Starting);
        match self.spawn_running().await {
            Ok(running) => {
                self.current = Some(running);
                self.state.set_status(CoreStatus::Running);
                Ok(())
            }
            Err(err) => {
                self.state.set_status(CoreStatus::Stopped);
                Err(err)
            }
        }
    }

    /// Heartbeat the live Core and return its health snapshot.
    ///
    /// # Errors
    /// Returns [`ShellError::Process`] if no Core is running, or the heartbeat's
    /// own error ([`ShellError::Timeout`]/[`ShellError::Ipc`]) if it does not
    /// answer.
    pub async fn health_check(&self) -> ShellResult<Value> {
        let running = self
            .current
            .as_ref()
            .ok_or_else(|| ShellError::Process("core is not running".to_owned()))?;
        running
            .channel
            .heartbeat(self.config.heartbeat_timeout)
            .await
    }

    /// Whether the Core process has exited (crash detection).
    ///
    /// Returns `true` when no Core is running or the process has an exit status.
    ///
    /// # Errors
    /// Returns [`ShellError::Process`] if the process status cannot be polled.
    pub fn has_exited(&mut self) -> ShellResult<bool> {
        match &mut self.current {
            Some(running) => Ok(running.process.try_status()?.is_some()),
            None => Ok(true),
        }
    }

    /// If the Core was meant to be running but its process has exited, mark it
    /// crashed and restart it. Returns whether a recovery restart happened.
    ///
    /// # Errors
    /// Returns the [`restart`](Self::restart) error if recovery is needed but the
    /// restart budget is exhausted or the respawn fails.
    pub async fn recover_if_crashed(&mut self) -> ShellResult<bool> {
        if self.state.status() != CoreStatus::Running {
            return Ok(false);
        }
        if !self.has_exited()? {
            return Ok(false);
        }
        self.state.set_status(CoreStatus::Crashed);
        self.restart().await?;
        Ok(true)
    }

    /// Restart the Core: stop the current process and spawn a fresh one.
    ///
    /// Enforces the restart budget *before* touching the running process, so a
    /// refusal leaves the current state untouched. On success the restart
    /// counter is bumped and the Core is `Running` again.
    ///
    /// # Errors
    /// Returns [`ShellError::Process`] if the restart budget is exhausted, or the
    /// respawn's error if the new process fails its startup health gate.
    pub async fn restart(&mut self) -> ShellResult<()> {
        if self.state.restart_count() >= self.config.max_restarts {
            return Err(ShellError::Process(format!(
                "restart budget of {} exhausted",
                self.config.max_restarts
            )));
        }
        self.state.set_status(CoreStatus::Restarting);
        self.stop_current().await;
        let running = self.spawn_running().await?;
        self.current = Some(running);
        self.state.record_restart();
        self.state.set_status(CoreStatus::Running);
        Ok(())
    }

    /// Shut the Core down cleanly and mark it stopped (no restart).
    ///
    /// # Errors
    /// Returns [`ShellError::Process`] if the underlying process shutdown fails.
    pub async fn shutdown(&mut self) -> ShellResult<()> {
        if let Some(mut running) = self.current.take() {
            let _ = running.channel.request("app.shutdown", None).await;
            drop(running.channel);
            running.process.shutdown().await?;
        }
        self.state.set_status(CoreStatus::Stopped);
        Ok(())
    }

    /// Spawn a Core, wire its channel, and gate on a startup heartbeat.
    async fn spawn_running(&self) -> ShellResult<Running> {
        let mut process = self.spec.spawn()?;
        let stdout = process
            .take_stdout()
            .ok_or_else(|| ShellError::Process("core stdout was not piped".to_owned()))?;
        let stdin = process
            .take_stdin()
            .ok_or_else(|| ShellError::Process("core stdin was not piped".to_owned()))?;
        let (channel, events) = CoreChannel::new(stdout, stdin);
        let channel = Arc::new(channel);

        if let Err(err) = channel.heartbeat(self.config.heartbeat_timeout).await {
            drop(channel);
            let _ = process.kill().await;
            return Err(err);
        }
        Ok(Running {
            process,
            channel,
            events: Some(events),
        })
    }

    /// Best-effort stop of the current process (used by shutdown/restart paths).
    async fn stop_current(&mut self) {
        if let Some(mut running) = self.current.take() {
            let _ = running.channel.request("app.shutdown", None).await;
            drop(running.channel);
            let _ = running.process.shutdown().await;
        }
    }
}

#[cfg(test)]
mod tests;
