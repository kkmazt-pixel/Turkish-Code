//! Shell error taxonomy — the single error type surfaced by the host.
//!
//! The shell is a thin host: it spawns the Core process, speaks the Core
//! Channel over stdio, and supervises the lifecycle. Every fallible *host*
//! operation surfaces as a [`ShellError`]. Business errors belong to the Python
//! Core and travel as IPC payloads; they are never rewritten into a
//! [`ShellError`].

use std::error::Error;
use std::fmt;

/// A host-side result carrying a [`ShellError`] on failure.
pub type ShellResult<T> = Result<T, ShellError>;

/// Errors raised by the Desktop Shell host.
///
/// The variants map to the host's responsibilities — process supervision, the
/// IPC transport, timeouts, permission bridging, and shell configuration — and
/// deliberately stop there. The enum is `#[non_exhaustive]` so later increments
/// can add variants without breaking downstream matches.
#[derive(Debug)]
#[non_exhaustive]
pub enum ShellError {
    /// The Core process could not be spawned, signalled, or reaped.
    Process(String),
    /// An IPC frame could not be encoded, decoded, or delivered.
    Ipc(String),
    /// The Core did not respond within the allotted time.
    Timeout(String),
    /// A host-side permission request was denied by the user or policy.
    PermissionDenied(String),
    /// Shell configuration was missing or invalid.
    Config(String),
}

impl ShellError {
    /// A short, stable machine-readable kind for this error.
    ///
    /// Useful for logging and for mapping a host error onto a UI channel
    /// without matching every variant at the call site.
    #[must_use]
    pub const fn kind(&self) -> &'static str {
        match self {
            Self::Process(_) => "process",
            Self::Ipc(_) => "ipc",
            Self::Timeout(_) => "timeout",
            Self::PermissionDenied(_) => "permission_denied",
            Self::Config(_) => "config",
        }
    }
}

impl fmt::Display for ShellError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let detail = match self {
            Self::Process(d)
            | Self::Ipc(d)
            | Self::Timeout(d)
            | Self::PermissionDenied(d)
            | Self::Config(d) => d,
        };
        write!(f, "{}: {detail}", self.kind())
    }
}

impl Error for ShellError {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn kind_is_stable_per_variant() {
        assert_eq!(ShellError::Process(String::new()).kind(), "process");
        assert_eq!(ShellError::Ipc(String::new()).kind(), "ipc");
        assert_eq!(ShellError::Timeout(String::new()).kind(), "timeout");
        assert_eq!(
            ShellError::PermissionDenied(String::new()).kind(),
            "permission_denied"
        );
        assert_eq!(ShellError::Config(String::new()).kind(), "config");
    }

    #[test]
    fn display_prefixes_kind_and_shows_detail() {
        let err = ShellError::Process("spawn failed".to_owned());
        assert_eq!(err.to_string(), "process: spawn failed");
    }

    #[test]
    fn is_a_std_error() {
        // Compiles only if `ShellError: std::error::Error`; also exercises the
        // trait-object path a host uses when boxing errors.
        let boxed: Box<dyn Error> = Box::new(ShellError::Ipc("bad frame".to_owned()));
        assert_eq!(boxed.to_string(), "ipc: bad frame");
    }
}
