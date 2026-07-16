//! Core process — spawning and supervising the Python Core as a child process.
//!
//! The shell runs the Python Core as a **separate process** and talks to it only
//! over stdio (the Core Channel, Phase 2). This module owns that OS boundary:
//! how the process is described ([`CoreSpec`]), how it is spawned, how its stdio
//! is handed to the IPC layer, and how it is shut down or killed. It knows
//! nothing about frames, requests, or business logic — those live above it
//! (Increment 3) and inside the Python Core.
//!
//! Restart and health policy belong to the lifecycle layer (Increment 4); this
//! module only provides the primitives it composes: spawn, `shutdown`, `kill`.

use std::ffi::OsString;
use std::path::PathBuf;
use std::process::{ExitStatus, Stdio};
use std::time::Duration;

use tokio::process::{Child, ChildStderr, ChildStdin, ChildStdout, Command};
use tokio::time::timeout;

use crate::errors::{ShellError, ShellResult};

/// The default grace period a graceful shutdown waits before killing the Core.
pub const DEFAULT_SHUTDOWN_GRACE: Duration = Duration::from_secs(5);

/// A declarative description of how to launch the Core process.
///
/// The spec is cloneable and side-effect free: the lifecycle layer keeps one
/// around and re-spawns from it on restart. Nothing here runs until
/// [`CoreProcess::spawn`] is called.
#[derive(Debug, Clone)]
pub struct CoreSpec {
    program: OsString,
    args: Vec<OsString>,
    working_dir: Option<PathBuf>,
    env: Vec<(OsString, OsString)>,
    shutdown_grace: Duration,
}

impl CoreSpec {
    /// Describe a Core launched by running `program` (e.g. a Python interpreter).
    #[must_use]
    pub fn new(program: impl Into<OsString>) -> Self {
        Self {
            program: program.into(),
            args: Vec::new(),
            working_dir: None,
            env: Vec::new(),
            shutdown_grace: DEFAULT_SHUTDOWN_GRACE,
        }
    }

    /// Append a single command-line argument.
    #[must_use]
    pub fn arg(mut self, arg: impl Into<OsString>) -> Self {
        self.args.push(arg.into());
        self
    }

    /// Append several command-line arguments in order.
    #[must_use]
    pub fn args<I, A>(mut self, args: I) -> Self
    where
        I: IntoIterator<Item = A>,
        A: Into<OsString>,
    {
        self.args.extend(args.into_iter().map(Into::into));
        self
    }

    /// Set the working directory the Core process is spawned in.
    #[must_use]
    pub fn current_dir(mut self, dir: impl Into<PathBuf>) -> Self {
        self.working_dir = Some(dir.into());
        self
    }

    /// Add an environment variable for the Core process.
    #[must_use]
    pub fn env(mut self, key: impl Into<OsString>, value: impl Into<OsString>) -> Self {
        self.env.push((key.into(), value.into()));
        self
    }

    /// Override how long a graceful shutdown waits before killing the Core.
    #[must_use]
    pub const fn shutdown_grace(mut self, grace: Duration) -> Self {
        self.shutdown_grace = grace;
        self
    }

    /// Spawn the Core process described by this spec.
    ///
    /// Convenience wrapper for [`CoreProcess::spawn`].
    ///
    /// # Errors
    /// Returns [`ShellError::Process`] if the process cannot be spawned.
    pub fn spawn(&self) -> ShellResult<CoreProcess> {
        CoreProcess::spawn(self)
    }
}

/// A running Core process together with its captured stdio.
///
/// The three stdio streams are handed out exactly once each via
/// [`take_stdin`](Self::take_stdin), [`take_stdout`](Self::take_stdout), and
/// [`take_stderr`](Self::take_stderr) so the IPC layer can own them without
/// aliasing. Whatever is not taken is closed on shutdown.
#[derive(Debug)]
pub struct CoreProcess {
    child: Child,
    stdin: Option<ChildStdin>,
    stdout: Option<ChildStdout>,
    stderr: Option<ChildStderr>,
    shutdown_grace: Duration,
}

impl CoreProcess {
    /// Spawn the Core process described by `spec`, piping all three stdio streams.
    ///
    /// # Errors
    /// Returns [`ShellError::Process`] if the OS refuses to spawn the process
    /// (for example, the program does not exist or is not executable).
    pub fn spawn(spec: &CoreSpec) -> ShellResult<Self> {
        let mut command = Command::new(&spec.program);
        command
            .args(&spec.args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);
        if let Some(dir) = &spec.working_dir {
            command.current_dir(dir);
        }
        for (key, value) in &spec.env {
            command.env(key, value);
        }

        let mut child = command
            .spawn()
            .map_err(|err| ShellError::Process(format!("could not spawn Core process: {err}")))?;

        // The three streams were requested as `piped`, so they are present.
        let stdin = child.stdin.take();
        let stdout = child.stdout.take();
        let stderr = child.stderr.take();
        Ok(Self {
            child,
            stdin,
            stdout,
            stderr,
            shutdown_grace: spec.shutdown_grace,
        })
    }

    /// The OS process id, or `None` if the process has already been reaped.
    #[must_use]
    pub fn id(&self) -> Option<u32> {
        self.child.id()
    }

    /// Take ownership of the Core's stdin (the request-writing half of IPC).
    pub fn take_stdin(&mut self) -> Option<ChildStdin> {
        self.stdin.take()
    }

    /// Take ownership of the Core's stdout (the response-reading half of IPC).
    pub fn take_stdout(&mut self) -> Option<ChildStdout> {
        self.stdout.take()
    }

    /// Take ownership of the Core's stderr (diagnostic log stream).
    pub fn take_stderr(&mut self) -> Option<ChildStderr> {
        self.stderr.take()
    }

    /// Check, without blocking, whether the Core has exited.
    ///
    /// # Errors
    /// Returns [`ShellError::Process`] if the process status cannot be queried.
    pub fn try_status(&mut self) -> ShellResult<Option<ExitStatus>> {
        self.child
            .try_wait()
            .map_err(|err| ShellError::Process(format!("could not poll Core status: {err}")))
    }

    /// Wait for the Core to exit on its own and return its exit status.
    ///
    /// # Errors
    /// Returns [`ShellError::Process`] if the process cannot be awaited.
    pub async fn wait(&mut self) -> ShellResult<ExitStatus> {
        self.child
            .wait()
            .await
            .map_err(|err| ShellError::Process(format!("could not wait for Core: {err}")))
    }

    /// Forcibly kill the Core process and reap it.
    ///
    /// # Errors
    /// Returns [`ShellError::Process`] if the kill or reap fails.
    pub async fn kill(&mut self) -> ShellResult<ExitStatus> {
        self.child
            .kill()
            .await
            .map_err(|err| ShellError::Process(format!("could not kill Core: {err}")))?;
        self.wait().await
    }

    /// Gracefully shut the Core down, killing it if it overruns the grace period.
    ///
    /// Closes stdin first — the Core Channel treats stdin EOF as "drain and
    /// exit" — then waits up to the configured grace period for a clean exit. If
    /// the process is still alive after that, it is killed. Returns the final
    /// exit status either way.
    ///
    /// # Errors
    /// Returns [`ShellError::Process`] if the process cannot be awaited or killed.
    pub async fn shutdown(&mut self) -> ShellResult<ExitStatus> {
        // Dropping stdin closes the pipe, signalling EOF to the Core.
        self.stdin = None;
        match timeout(self.shutdown_grace, self.child.wait()).await {
            Ok(status) => status.map_err(|err| {
                ShellError::Process(format!("could not wait for Core shutdown: {err}"))
            }),
            Err(_elapsed) => self.kill().await,
        }
    }
}

#[cfg(test)]
mod tests;
