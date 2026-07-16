//! Core bridge — the runtime wiring between the Core and the host (doc 08 §6).
//!
//! Starting the Core yields two inbound streams: notifications (Core→UI events)
//! and Core→shell requests (permission/tool asks). [`CoreBridge`] attaches the
//! background workers that service them — the [`PermissionBridge`] answering
//! requests and [`forward_events`] re-emitting notifications onto an
//! [`EventSink`] — and tracks their task handles so they can be torn down and
//! re-attached across a Core restart (each restart mints fresh streams).
//!
//! The bridge is intentionally ignorant of the lifecycle: it is handed a live
//! channel and its events and wires them up. Deciding *when* to (re)attach is
//! the composition's job ([`crate::app`]).

use std::sync::{Arc, Mutex};

use tokio::task::JoinHandle;

use crate::events::{forward_events, EventSink};
use crate::ipc::{CoreChannel, CoreEvents};
use crate::permissions::{PermissionBridge, PermissionResponder};

/// Wires a running Core's inbound streams to their background workers.
pub struct CoreBridge<R: PermissionResponder, S: EventSink> {
    responder: Arc<R>,
    sink: Arc<S>,
    tasks: Mutex<Vec<JoinHandle<()>>>,
}

impl<R, S> CoreBridge<R, S>
where
    R: PermissionResponder + Send + Sync + 'static,
    S: EventSink + 'static,
{
    /// Build a bridge that answers permission requests with `responder` and
    /// re-emits Core notifications onto `sink`.
    pub fn new(responder: R, sink: S) -> Self {
        Self {
            responder: Arc::new(responder),
            sink: Arc::new(sink),
            tasks: Mutex::new(Vec::new()),
        }
    }

    /// Attach workers to a live `channel` and its `events`, replacing any
    /// previously attached ones (used on first start and after each restart).
    pub fn attach(&self, channel: Arc<CoreChannel>, events: CoreEvents) {
        self.abort();
        let CoreEvents {
            notifications,
            requests,
        } = events;

        let permission = PermissionBridge::new(channel, Arc::clone(&self.responder));
        let permission_task = tokio::spawn(async move { permission.run(requests).await });
        let forward_task = tokio::spawn(forward_events(Arc::clone(&self.sink), notifications));

        let mut tasks = self.tasks.lock().expect("bridge task mutex");
        tasks.push(permission_task);
        tasks.push(forward_task);
    }

    /// Abort all attached workers (on shutdown, or before re-attaching).
    pub fn abort(&self) {
        for task in self.tasks.lock().expect("bridge task mutex").drain(..) {
            task.abort();
        }
    }

    /// How many workers are currently attached (two when wired: permission +
    /// forwarder). Primarily for tests and diagnostics.
    #[must_use]
    pub fn attached_worker_count(&self) -> usize {
        self.tasks.lock().expect("bridge task mutex").len()
    }
}

impl<R: PermissionResponder, S: EventSink> Drop for CoreBridge<R, S> {
    fn drop(&mut self) {
        for task in self.tasks.lock().expect("bridge task mutex").drain(..) {
            task.abort();
        }
    }
}
