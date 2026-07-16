//! Permission bridge — the shell answers the Core's `permission.request` (doc 24).
//!
//! Every side effect the Core wants to perform (filesystem, clipboard, OS
//! notifications, native dialogs) is routed through the Kabuk as a Core→shell
//! JSON-RPC request (doc 10 §6.3); the shell is the choke point that decides
//! *allow* or *deny* and answers. This module holds that policy plumbing:
//!
//! - [`Capability`] — the gated capability taxonomy (doc 24 §4);
//! - [`Decision`] — allow / deny, with **fail-safe deny** on any ambiguity;
//! - [`PermissionResponder`] — the port that makes a decision. The headless
//!   [`PolicyResponder`] evaluates mode + standing grants; the **native
//!   permission request** (an OS dialog/notification prompt) is a Tauri-side
//!   implementation of this same port, plugged in later (DIP);
//! - [`PermissionBridge`] — pulls Core→shell requests and answers each.
//!
//! The shell never *performs* the effect (that is the Core/broker's job); it
//! only decides whether it may happen (doc 24 §9, PR-1/PR-2).

use std::future::Future;

use serde_json::{json, Value};

use crate::ipc::CoreChannel;
use crate::message::Request;

/// The JSON-RPC method the Core uses to ask the shell for permission (doc 24 §6).
pub const PERMISSION_REQUEST_METHOD: &str = "permission.request";

/// JSON-RPC "method not found" code, returned for unhandled Core→shell methods.
pub const METHOD_NOT_FOUND: i64 = -32601;

/// A gated capability the Core may request (doc 24 §4).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Capability {
    /// Reading or writing user files.
    Filesystem,
    /// Reading or writing the system clipboard.
    Clipboard,
    /// Posting an OS notification.
    Notifications,
    /// Opening a native dialog (open/save/message).
    Dialog,
}

impl Capability {
    /// Parse a capability id as sent by the Core, or `None` if unrecognised.
    ///
    /// Accepts the doc 24 fine-grained filesystem ids (`fs.read`/`fs.write`) as
    /// well as the coarse category names.
    #[must_use]
    pub fn parse(id: &str) -> Option<Self> {
        match id {
            "filesystem" | "fs" | "fs.read" | "fs.write" => Some(Self::Filesystem),
            "clipboard" => Some(Self::Clipboard),
            "notifications" | "notification" => Some(Self::Notifications),
            "dialog" => Some(Self::Dialog),
            _ => None,
        }
    }

    /// The canonical category name.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Filesystem => "filesystem",
            Self::Clipboard => "clipboard",
            Self::Notifications => "notifications",
            Self::Dialog => "dialog",
        }
    }

    /// Whether this capability is privacy/safety-sensitive (doc 24 §5).
    ///
    /// Sensitive capabilities are denied without a standing grant when no user
    /// prompt can answer (the headless fail-safe); benign ones are allowed.
    #[must_use]
    pub const fn is_sensitive(self) -> bool {
        matches!(self, Self::Filesystem | Self::Clipboard)
    }
}

/// The permission mode in effect for a session (doc 24 §5).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum PermissionMode {
    /// Plan: block every gated effect that is not already granted.
    Plan,
    /// Ask (default): benign effects allowed; sensitive ones need a prompt,
    /// which — with no UI attached — falls back to deny.
    #[default]
    Ask,
    /// Auto: pre-granted scopes allowed; benign effects allowed.
    Auto,
}

/// The outcome of a permission request.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Decision {
    /// The effect may proceed.
    Allow,
    /// The effect is refused (the fail-safe default).
    Deny,
}

impl Decision {
    /// The wire token (`"allow"`/`"deny"`) sent back to the Core.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Allow => "allow",
            Self::Deny => "deny",
        }
    }
}

/// A parsed `permission.request` from the Core.
#[derive(Debug, Clone)]
pub struct PermissionRequest {
    /// The capability being requested.
    pub capability: Capability,
    /// The precise target (path/host/command), if the Core supplied one.
    pub target: Option<String>,
    /// A human-readable reason to show in a prompt, if supplied.
    pub reason: Option<String>,
}

impl PermissionRequest {
    /// Parse the `params` of a `permission.request`, or `None` if malformed or
    /// the capability is unrecognised (the caller then fails safe to deny).
    #[must_use]
    pub fn from_params(params: Option<&Value>) -> Option<Self> {
        let params = params?.as_object()?;
        let capability = Capability::parse(params.get("capability")?.as_str()?)?;
        Some(Self {
            capability,
            target: params
                .get("target")
                .and_then(Value::as_str)
                .map(str::to_owned),
            reason: params
                .get("reason")
                .and_then(Value::as_str)
                .map(str::to_owned),
        })
    }
}

/// A port that decides a permission request (doc 24 §6).
///
/// The headless [`PolicyResponder`] implements it with mode + grants; a Tauri
/// responder implements it with a native OS prompt. Either way the bridge only
/// depends on this trait (DIP).
pub trait PermissionResponder {
    /// Decide whether `request` may proceed.
    fn decide(&self, request: &PermissionRequest) -> impl Future<Output = Decision> + Send;
}

/// The headless policy responder: mode + standing grants, fail-safe deny.
///
/// Evaluation follows doc 24 §6: a matching standing grant allows; otherwise the
/// mode decides, with sensitive capabilities denied when only a user prompt
/// could allow them (no UI is attached here — that is the Tauri responder's
/// role).
#[derive(Debug, Clone, Default)]
pub struct PolicyResponder {
    mode: PermissionMode,
    grants: Vec<Capability>,
}

impl PolicyResponder {
    /// A responder in `mode` with no standing grants.
    #[must_use]
    pub fn new(mode: PermissionMode) -> Self {
        Self {
            mode,
            grants: Vec::new(),
        }
    }

    /// Add a standing grant for `capability` (doc 24 §8), returning `self`.
    #[must_use]
    pub fn with_grant(mut self, capability: Capability) -> Self {
        if !self.grants.contains(&capability) {
            self.grants.push(capability);
        }
        self
    }

    /// Evaluate the decision synchronously (grant-first, then mode).
    #[must_use]
    pub fn evaluate(&self, request: &PermissionRequest) -> Decision {
        if self.grants.contains(&request.capability) {
            return Decision::Allow;
        }
        match self.mode {
            PermissionMode::Plan => Decision::Deny,
            PermissionMode::Ask | PermissionMode::Auto => {
                if request.capability.is_sensitive() {
                    Decision::Deny
                } else {
                    Decision::Allow
                }
            }
        }
    }
}

impl PermissionResponder for PolicyResponder {
    async fn decide(&self, request: &PermissionRequest) -> Decision {
        self.evaluate(request)
    }
}

impl<R: PermissionResponder + Sync + ?Sized> PermissionResponder for std::sync::Arc<R> {
    fn decide(&self, request: &PermissionRequest) -> impl Future<Output = Decision> + Send {
        (**self).decide(request)
    }
}

/// Bridges Core→shell requests to a [`PermissionResponder`] and answers them.
pub struct PermissionBridge<R: PermissionResponder> {
    channel: std::sync::Arc<CoreChannel>,
    responder: R,
}

impl<R: PermissionResponder> PermissionBridge<R> {
    /// Wire a bridge that answers on `channel` using `responder`.
    pub fn new(channel: std::sync::Arc<CoreChannel>, responder: R) -> Self {
        Self { channel, responder }
    }

    /// Handle one inbound Core→shell request, answering it on the channel.
    ///
    /// A `permission.request` is decided and answered `{ "decision": … }`. A
    /// malformed request fails safe to deny. Any other method is answered with a
    /// method-not-found error so the Core is never left hanging.
    ///
    /// # Errors
    /// Returns [`ShellError::Ipc`](crate::ShellError::Ipc) if the response cannot
    /// be written.
    pub async fn handle(&self, request: Request) -> crate::ShellResult<()> {
        if request.method != PERMISSION_REQUEST_METHOD {
            return self
                .channel
                .respond_error(
                    &request.id,
                    METHOD_NOT_FOUND,
                    "unhandled Core→shell method",
                    Some(json!({ "method": request.method })),
                )
                .await;
        }

        let decision = match PermissionRequest::from_params(request.params.as_ref()) {
            Some(parsed) => self.responder.decide(&parsed).await,
            // Ambiguity fails safe (doc 24 §7).
            None => Decision::Deny,
        };
        self.channel
            .respond(&request.id, json!({ "decision": decision.as_str() }))
            .await
    }

    /// Serve permission requests until the inbound stream ends.
    pub async fn run(&self, mut requests: tokio::sync::mpsc::UnboundedReceiver<Request>) {
        while let Some(request) = requests.recv().await {
            let _ = self.handle(request).await;
        }
    }
}

#[cfg(test)]
mod tests;
