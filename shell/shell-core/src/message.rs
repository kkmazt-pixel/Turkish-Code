//! JSON-RPC 2.0 message envelopes for the Core Channel (doc 10 §6.2).
//!
//! These types mirror the Python Core's `kanal.mesaj` wire shapes and the
//! `kanal.dogrulama` classification rules exactly — the shell is a peer on the
//! same protocol, not the author of a new one. Payloads (`params`, `result`,
//! error `data`) are arbitrary JSON and stay as [`serde_json::Value`]; the shell
//! is a transport host and does not interpret Core business payloads.

use serde_json::{Map, Value};

use crate::errors::{ShellError, ShellResult};

/// The only JSON-RPC version the Core Channel speaks.
pub const JSONRPC_VERSION: &str = "2.0";

/// The Core Channel contract version the shell targets (doc 10 §13), sent as
/// `protocolVersion` in `app.handshake`.
pub const PROTOCOL_VERSION: &str = "1.0.0";

/// A JSON-RPC request expecting a correlated response.
///
/// `id` is kept as a [`Value`] so an inbound request's id can be echoed back
/// with its exact JSON type; the shell's own outbound requests always use a
/// string id.
#[derive(Debug, Clone)]
pub struct Request {
    pub id: Value,
    pub method: String,
    pub params: Option<Value>,
    pub meta: Option<Value>,
}

impl Request {
    /// Build an outbound request with a string `id`.
    #[must_use]
    pub fn new(id: impl Into<String>, method: impl Into<String>, params: Option<Value>) -> Self {
        Self {
            id: Value::String(id.into()),
            method: method.into(),
            params,
            meta: None,
        }
    }

    /// Serialize to the JSON-RPC request envelope.
    #[must_use]
    pub fn to_wire(&self) -> Value {
        let mut wire = Map::new();
        wire.insert("jsonrpc".to_owned(), Value::from(JSONRPC_VERSION));
        wire.insert("id".to_owned(), self.id.clone());
        wire.insert("method".to_owned(), Value::from(self.method.clone()));
        if let Some(params) = &self.params {
            wire.insert("params".to_owned(), params.clone());
        }
        if let Some(meta) = &self.meta {
            wire.insert("meta".to_owned(), meta.clone());
        }
        Value::Object(wire)
    }
}

/// A JSON-RPC notification: a method call with no id and no response.
#[derive(Debug, Clone)]
pub struct Notification {
    pub method: String,
    pub params: Option<Value>,
}

impl Notification {
    /// Build a notification.
    #[must_use]
    pub fn new(method: impl Into<String>, params: Option<Value>) -> Self {
        Self {
            method: method.into(),
            params,
        }
    }

    /// Serialize to the JSON-RPC notification envelope.
    #[must_use]
    pub fn to_wire(&self) -> Value {
        let mut wire = Map::new();
        wire.insert("jsonrpc".to_owned(), Value::from(JSONRPC_VERSION));
        wire.insert("method".to_owned(), Value::from(self.method.clone()));
        if let Some(params) = &self.params {
            wire.insert("params".to_owned(), params.clone());
        }
        Value::Object(wire)
    }
}

/// The `error` member of a JSON-RPC error response (doc 10 §14).
#[derive(Debug, Clone)]
pub struct JsonRpcError {
    pub code: i64,
    pub message: String,
    pub data: Option<Value>,
}

/// The outcome of a request: a success `result` or a typed error.
#[derive(Debug, Clone)]
pub enum Response {
    /// A successful response carrying its `result` payload.
    Success(Value),
    /// A failed response carrying the JSON-RPC error object.
    Error(JsonRpcError),
}

/// A parsed inbound frame: which of the four JSON-RPC shapes it is.
#[derive(Debug, Clone)]
pub enum Incoming {
    /// A request from the Core (Ç→K, e.g. `tool.invoke`) we must answer.
    Request(Request),
    /// A stream/event notification.
    Notification(Notification),
    /// A response correlated to one of our outbound requests.
    Response { id: Value, body: Response },
}

/// Serialize any JSON [`Value`] envelope to UTF-8 bytes for a frame.
#[must_use]
pub fn to_bytes(wire: &Value) -> Vec<u8> {
    // A `Value` built from owned data always serializes; `to_vec` cannot fail here.
    serde_json::to_vec(wire).expect("a serde_json::Value always serializes")
}

/// A stable string key for a request id, used to correlate responses.
///
/// String ids (what the shell sends) map to themselves; numeric or other ids
/// fall back to their canonical JSON text, so correlation is total.
#[must_use]
pub fn id_key(id: &Value) -> String {
    match id {
        Value::String(text) => text.clone(),
        other => other.to_string(),
    }
}

/// Parse one frame payload into a typed [`Incoming`] message (doc 10 §6.2).
///
/// Mirrors the Core's `dogrulama.parse_frame` classification: valid JSON object,
/// `jsonrpc == "2.0"`, then request / notification / response by field shape.
///
/// # Errors
/// Returns [`ShellError::Ipc`] if the bytes are not a JSON object, use an
/// unsupported `jsonrpc` version, or match no known message shape.
pub fn parse(payload: &[u8]) -> ShellResult<Incoming> {
    let value: Value = serde_json::from_slice(payload)
        .map_err(|err| ShellError::Ipc(format!("invalid JSON in frame: {err}")))?;
    let object = value
        .as_object()
        .ok_or_else(|| ShellError::Ipc("frame is not a JSON object".to_owned()))?;

    if object.get("jsonrpc").and_then(Value::as_str) != Some(JSONRPC_VERSION) {
        return Err(ShellError::Ipc(
            "unsupported or missing jsonrpc version".to_owned(),
        ));
    }

    let has_id = object.contains_key("id");
    if let Some(method) = object.get("method") {
        let method = method
            .as_str()
            .ok_or_else(|| ShellError::Ipc("method must be a string".to_owned()))?
            .to_owned();
        let params = object.get("params").cloned();
        if has_id {
            return Ok(Incoming::Request(Request {
                id: object["id"].clone(),
                method,
                params,
                meta: object.get("meta").cloned(),
            }));
        }
        return Ok(Incoming::Notification(Notification { method, params }));
    }

    if has_id && object.contains_key("result") {
        return Ok(Incoming::Response {
            id: object["id"].clone(),
            body: Response::Success(object["result"].clone()),
        });
    }

    if let Some(error) = object.get("error") {
        return Ok(Incoming::Response {
            id: object.get("id").cloned().unwrap_or(Value::Null),
            body: Response::Error(parse_error(error)?),
        });
    }

    Err(ShellError::Ipc(
        "frame matches no known JSON-RPC message shape".to_owned(),
    ))
}

fn parse_error(error: &Value) -> ShellResult<JsonRpcError> {
    let object = error
        .as_object()
        .ok_or_else(|| ShellError::Ipc("malformed error object".to_owned()))?;
    let code = object
        .get("code")
        .and_then(Value::as_i64)
        .ok_or_else(|| ShellError::Ipc("error object missing integer code".to_owned()))?;
    let message = object
        .get("message")
        .and_then(Value::as_str)
        .ok_or_else(|| ShellError::Ipc("error object missing string message".to_owned()))?
        .to_owned();
    Ok(JsonRpcError {
        code,
        message,
        data: object.get("data").cloned(),
    })
}

/// Build a JSON-RPC success-response envelope correlated by `id`.
#[must_use]
pub fn success_wire(id: &Value, result: Value) -> Value {
    let mut wire = Map::new();
    wire.insert("jsonrpc".to_owned(), Value::from(JSONRPC_VERSION));
    wire.insert("id".to_owned(), id.clone());
    wire.insert("result".to_owned(), result);
    Value::Object(wire)
}

/// Build a JSON-RPC error-response envelope correlated by `id` (doc 10 §14).
#[must_use]
pub fn error_wire(id: &Value, code: i64, message: &str, data: Option<Value>) -> Value {
    let mut error = Map::new();
    error.insert("code".to_owned(), Value::from(code));
    error.insert("message".to_owned(), Value::from(message.to_owned()));
    if let Some(data) = data {
        error.insert("data".to_owned(), data);
    }
    let mut wire = Map::new();
    wire.insert("jsonrpc".to_owned(), Value::from(JSONRPC_VERSION));
    wire.insert("id".to_owned(), id.clone());
    wire.insert("error".to_owned(), Value::Object(error));
    Value::Object(wire)
}

#[cfg(test)]
mod tests;
