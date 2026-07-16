//! Event plane — forwarding Core notifications out to the UI (doc 10 §8, doc 08 §6).
//!
//! The Core streams notifications (token deltas, reasoning steps, health
//! changes) as JSON-RPC notifications; the Kabuk re-emits each as a Bridge event
//! to the Arayüz. This module owns that re-emission as a DIP seam: [`EventSink`]
//! is the port, and the Tauri binary implements it with `AppHandle::emit`.
//! [`forward_events`] drains a Core notification stream and re-emits every frame
//! onto the sink, preserving method name and payload — it adds no logic, so it
//! is testable with an in-memory sink and no webview.

use serde_json::Value;
use tokio::sync::mpsc::UnboundedReceiver;

use crate::message::Notification;

/// A destination for re-emitted Core notifications (doc 08 §6).
///
/// The Tauri binary implements this over `AppHandle::emit(name, payload)`; tests
/// implement it with a collecting buffer. `Send + Sync` so the forwarder can run
/// in a background task.
pub trait EventSink: Send + Sync {
    /// Emit one event: an event `name` and its JSON `payload`.
    fn emit(&self, name: &str, payload: &Value);
}

impl<S: EventSink + ?Sized> EventSink for std::sync::Arc<S> {
    fn emit(&self, name: &str, payload: &Value) {
        (**self).emit(name, payload);
    }
}

/// Drain `notifications` and re-emit each onto `sink` until the stream ends.
///
/// A notification with no params is emitted with a JSON `null` payload. Runs
/// until the Core channel closes (the sender is dropped), which is the natural
/// shutdown signal for the forwarding task.
pub async fn forward_events<S: EventSink>(
    sink: S,
    mut notifications: UnboundedReceiver<Notification>,
) {
    while let Some(note) = notifications.recv().await {
        let payload = note.params.unwrap_or(Value::Null);
        sink.emit(&note.method, &payload);
    }
}

#[cfg(test)]
mod tests;
