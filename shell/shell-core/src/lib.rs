//! turkish.code Desktop Shell — host-side core library (Phase 12).
//!
//! `shell-core` is the pure-Rust heart of the Desktop Shell. It spawns and
//! supervises the Python Core process, speaks the Core Channel (Phase 2) over
//! stdio, drives the process lifecycle, and bridges OS permission requests to
//! the host. It contains **no business logic and no Tauri or UI dependency**:
//! providers, storage, conversation, agents, skills, and tools all live in the
//! Python Core and are reached only over IPC. The Tauri binary crate is a thin
//! glue layer built on top of this library and is added in a later increment.
//!
//! This module is the crate skeleton (Increment 1): only the shared
//! [`errors`] taxonomy and the supervised [`state`] are defined here; the
//! process, IPC, lifecycle, and permission layers arrive in later increments.

pub mod app;
pub mod bridge;
pub mod commands;
pub mod core_process;
pub mod errors;
pub mod events;
pub mod frame;
pub mod ipc;
pub mod lifecycle;
pub mod message;
pub mod permissions;
pub mod state;

pub use app::DesktopApp;
pub use bridge::CoreBridge;
pub use commands::ShellApi;
pub use core_process::{CoreProcess, CoreSpec, DEFAULT_SHUTDOWN_GRACE};
pub use errors::{ShellError, ShellResult};
pub use events::{forward_events, EventSink};
pub use ipc::{CoreChannel, CoreEvents};
pub use lifecycle::{CoreLifecycle, LifecycleConfig};
pub use message::{Incoming, JsonRpcError, Notification, Request, Response, PROTOCOL_VERSION};
pub use permissions::{
    Capability, Decision, PermissionBridge, PermissionMode, PermissionRequest, PermissionResponder,
    PolicyResponder,
};
pub use state::{CoreStatus, ShellState, WindowState};
