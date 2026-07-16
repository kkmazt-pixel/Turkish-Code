//! IPC bridge — the shell's client over the Core Channel (doc 10).
//!
//! [`CoreChannel`] drives one Core process's stdio: it writes framed JSON-RPC
//! requests and notifications, runs a background reader task that demultiplexes
//! inbound frames by shape, and correlates responses to their requests by `id`
//! (no head-of-line blocking — many requests may be in flight). Inbound
//! notifications and Core→shell requests are surfaced on [`CoreEvents`] for
//! higher layers (streaming, the permission bridge) to consume.
//!
//! This layer owns *transport plumbing only*. It does not know what any method
//! does; that is the Python Core's job. The framing and message shapes come
//! straight from [`crate::frame`] and [`crate::message`] — no new protocol.

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde_json::Value;
use tokio::io::{AsyncRead, AsyncWrite};
use tokio::sync::{mpsc, oneshot, Mutex as AsyncMutex};
use tokio::task::JoinHandle;
use tokio::time::timeout;

use crate::errors::{ShellError, ShellResult};
use crate::frame::{read_frame, write_frame};
use crate::message::{
    error_wire, id_key, parse, success_wire, to_bytes, Incoming, Notification, Request, Response,
};

type BoxWrite = Box<dyn AsyncWrite + Unpin + Send>;
type BoxRead = Box<dyn AsyncRead + Unpin + Send>;
type PendingMap = Mutex<HashMap<String, oneshot::Sender<Response>>>;

/// The inbound side of the channel: notifications and Core→shell requests.
///
/// Returned once at construction. Higher layers own it and pull from it; the
/// reader task pushes onto it. Unbounded because the reader must never block on
/// a slow consumer (bounded backpressure is a later concern).
pub struct CoreEvents {
    /// Stream/event notifications from the Core (no response expected).
    pub notifications: mpsc::UnboundedReceiver<Notification>,
    /// Requests the Core sends to the shell (Ç→K, e.g. `tool.invoke`), which
    /// the permission/tool bridge answers in a later increment.
    pub requests: mpsc::UnboundedReceiver<Request>,
}

/// Shared state between the public handle and the background reader task.
struct Shared {
    writer: AsyncMutex<BoxWrite>,
    pending: PendingMap,
    next_id: AtomicU64,
}

/// A client handle over one Core process's Core Channel.
pub struct CoreChannel {
    shared: Arc<Shared>,
    reader: JoinHandle<()>,
}

impl CoreChannel {
    /// Wire a channel over a Core's stdout (`reader`) and stdin (`writer`).
    ///
    /// Spawns the background reader task immediately and hands back the
    /// [`CoreEvents`] inbound side. Typically the reader is
    /// [`CoreProcess::take_stdout`](crate::CoreProcess::take_stdout) and the
    /// writer is [`CoreProcess::take_stdin`](crate::CoreProcess::take_stdin).
    pub fn new<R, W>(reader: R, writer: W) -> (Self, CoreEvents)
    where
        R: AsyncRead + Unpin + Send + 'static,
        W: AsyncWrite + Unpin + Send + 'static,
    {
        let shared = Arc::new(Shared {
            writer: AsyncMutex::new(Box::new(writer) as BoxWrite),
            pending: Mutex::new(HashMap::new()),
            next_id: AtomicU64::new(0),
        });
        let (note_tx, note_rx) = mpsc::unbounded_channel();
        let (req_tx, req_rx) = mpsc::unbounded_channel();
        let reader_shared = Arc::clone(&shared);
        let reader = tokio::spawn(read_loop(
            Box::new(reader) as BoxRead,
            reader_shared,
            note_tx,
            req_tx,
        ));
        (
            Self { shared, reader },
            CoreEvents {
                notifications: note_rx,
                requests: req_rx,
            },
        )
    }

    /// Send a request and await its correlated response, with no time limit.
    ///
    /// # Errors
    /// Returns [`ShellError::Ipc`] if the request cannot be written or the
    /// channel closes before the response arrives.
    pub async fn request(&self, method: &str, params: Option<Value>) -> ShellResult<Response> {
        self.request_within(method, params, None).await
    }

    /// Send a request and await its response, failing after `deadline`.
    ///
    /// # Errors
    /// Returns [`ShellError::Timeout`] if `deadline` elapses first, or
    /// [`ShellError::Ipc`] on a transport failure or a closed channel.
    pub async fn request_timeout(
        &self,
        method: &str,
        params: Option<Value>,
        deadline: Duration,
    ) -> ShellResult<Response> {
        self.request_within(method, params, Some(deadline)).await
    }

    async fn request_within(
        &self,
        method: &str,
        params: Option<Value>,
        deadline: Option<Duration>,
    ) -> ShellResult<Response> {
        let id = format!(
            "kabuk-{}",
            self.shared.next_id.fetch_add(1, Ordering::Relaxed)
        );
        let (tx, rx) = oneshot::channel();
        self.insert_pending(&id, tx);

        let request = Request::new(id.clone(), method, params);
        if let Err(err) = self.write_wire(&request.to_wire()).await {
            self.remove_pending(&id);
            return Err(err);
        }

        match deadline {
            None => rx.await.map_err(|_| channel_closed()),
            Some(deadline) => match timeout(deadline, rx).await {
                Ok(received) => received.map_err(|_| channel_closed()),
                Err(_elapsed) => {
                    self.remove_pending(&id);
                    Err(ShellError::Timeout(format!(
                        "no response to '{method}' within {deadline:?}"
                    )))
                }
            },
        }
    }

    /// Send a fire-and-forget notification (no response expected).
    ///
    /// # Errors
    /// Returns [`ShellError::Ipc`] if the notification cannot be written.
    pub async fn notify(&self, method: &str, params: Option<Value>) -> ShellResult<()> {
        self.write_wire(&Notification::new(method, params).to_wire())
            .await
    }

    /// Answer an inbound Core→shell request (`id`) with a success result.
    ///
    /// # Errors
    /// Returns [`ShellError::Ipc`] if the response cannot be written.
    pub async fn respond(&self, id: &Value, result: Value) -> ShellResult<()> {
        self.write_wire(&success_wire(id, result)).await
    }

    /// Answer an inbound Core→shell request (`id`) with a typed error.
    ///
    /// # Errors
    /// Returns [`ShellError::Ipc`] if the response cannot be written.
    pub async fn respond_error(
        &self,
        id: &Value,
        code: i64,
        message: &str,
        data: Option<Value>,
    ) -> ShellResult<()> {
        self.write_wire(&error_wire(id, code, message, data)).await
    }

    /// Heartbeat the Core via `app.health`, returning its health snapshot.
    ///
    /// A successful response proves the Core process is alive and its channel is
    /// answering — the primitive the lifecycle layer polls on.
    ///
    /// # Errors
    /// Returns [`ShellError::Timeout`] if the Core does not answer in time, or
    /// [`ShellError::Ipc`] if it answers with an error or the channel is closed.
    pub async fn heartbeat(&self, deadline: Duration) -> ShellResult<Value> {
        match self.request_timeout("app.health", None, deadline).await? {
            Response::Success(result) => Ok(result),
            Response::Error(err) => Err(ShellError::Ipc(format!(
                "health check failed: {} (code {})",
                err.message, err.code
            ))),
        }
    }

    async fn write_wire(&self, wire: &Value) -> ShellResult<()> {
        let bytes = to_bytes(wire);
        let mut writer = self.shared.writer.lock().await;
        write_frame(&mut *writer, &bytes).await
    }

    fn insert_pending(&self, id: &str, tx: oneshot::Sender<Response>) {
        self.shared
            .pending
            .lock()
            .expect("pending mutex is never poisoned")
            .insert(id.to_owned(), tx);
    }

    fn remove_pending(&self, id: &str) {
        self.shared
            .pending
            .lock()
            .expect("pending mutex is never poisoned")
            .remove(id);
    }
}

impl Drop for CoreChannel {
    fn drop(&mut self) {
        // Stop reading once no one holds the channel; the writer half closes with
        // the shared state, signalling EOF to the Core.
        self.reader.abort();
    }
}

fn channel_closed() -> ShellError {
    ShellError::Ipc("core channel closed before responding".to_owned())
}

/// Background task: read frames, demultiplex, and route them.
async fn read_loop(
    mut reader: BoxRead,
    shared: Arc<Shared>,
    notifications: mpsc::UnboundedSender<Notification>,
    requests: mpsc::UnboundedSender<Request>,
) {
    // A clean EOF (`Ok(None)`) or a transport error both end the loop.
    while let Ok(Some(payload)) = read_frame(&mut reader).await {
        route(&payload, &shared, &notifications, &requests);
    }
    // Fail every still-pending request so awaiters unblock instead of hanging.
    shared
        .pending
        .lock()
        .expect("pending mutex is never poisoned")
        .clear();
}

fn route(
    payload: &[u8],
    shared: &Shared,
    notifications: &mpsc::UnboundedSender<Notification>,
    requests: &mpsc::UnboundedSender<Request>,
) {
    match parse(payload) {
        Ok(Incoming::Response { id, body }) => {
            if let Some(tx) = shared
                .pending
                .lock()
                .expect("pending mutex is never poisoned")
                .remove(&id_key(&id))
            {
                let _ = tx.send(body);
            }
        }
        Ok(Incoming::Notification(note)) => {
            let _ = notifications.send(note);
        }
        Ok(Incoming::Request(request)) => {
            let _ = requests.send(request);
        }
        // A malformed frame is dropped, never fatal — mirrors the Core (doc 10 §14).
        Err(_) => {}
    }
}

#[cfg(test)]
mod tests;
