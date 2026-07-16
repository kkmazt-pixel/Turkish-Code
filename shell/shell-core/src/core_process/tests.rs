//! Unit tests for [`super`] — real `python3` child processes, minimal mocking.

use super::*;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};

/// A [`CoreSpec`] that runs an inline Python program as a fake Core.
fn python(script: &str) -> CoreSpec {
    CoreSpec::new("python3").arg("-c").arg(script)
}

async fn read_first_line(stream: impl tokio::io::AsyncRead + Unpin) -> String {
    let mut lines = BufReader::new(stream).lines();
    lines
        .next_line()
        .await
        .expect("read line")
        .expect("a line was produced")
}

#[tokio::test]
async fn spawn_captures_stdout() {
    let mut core = python("print('hello-core')").spawn().expect("spawn");
    let stdout = core.take_stdout().expect("stdout piped");
    assert_eq!(read_first_line(stdout).await, "hello-core");
    core.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn spawn_captures_stderr() {
    let mut core = python("import sys; print('boom', file=sys.stderr)")
        .spawn()
        .expect("spawn");
    let stderr = core.take_stderr().expect("stderr piped");
    assert_eq!(read_first_line(stderr).await, "boom");
    core.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn spawn_reports_a_pid() {
    let mut core = python("import time; time.sleep(5)").spawn().expect("spawn");
    assert!(core.id().is_some());
    core.kill().await.expect("kill");
}

#[tokio::test]
async fn spawning_a_missing_program_errors() {
    let err = CoreSpec::new("definitely-not-a-real-program-xyz")
        .spawn()
        .expect_err("spawn should fail");
    assert_eq!(err.kind(), "process");
}

#[tokio::test]
async fn shutdown_lets_a_cooperative_core_exit_cleanly() {
    // Reads stdin to EOF, then exits 0 — the cooperative Core contract.
    let mut core = python("import sys; sys.stdin.read()")
        .spawn()
        .expect("spawn");
    let status = core.shutdown().await.expect("shutdown");
    assert!(status.success());
}

#[tokio::test]
async fn shutdown_kills_a_core_that_ignores_eof() {
    let spec = python("import time; time.sleep(30)").shutdown_grace(Duration::from_millis(150));
    let mut core = spec.spawn().expect("spawn");
    let status = core.shutdown().await.expect("shutdown");
    // Killed by signal, so it did not exit successfully.
    assert!(!status.success());
}

#[tokio::test]
async fn a_spec_can_respawn_after_shutdown() {
    // Restart primitive: the same spec yields a fresh, working process.
    let spec = python("print('gen')");
    let mut first = spec.spawn().expect("first spawn");
    first.shutdown().await.expect("first shutdown");

    let mut second = spec.spawn().expect("second spawn");
    let stdout = second.take_stdout().expect("stdout");
    assert_eq!(read_first_line(stdout).await, "gen");
    second.shutdown().await.expect("second shutdown");
}

#[tokio::test]
async fn stdin_can_be_taken_and_written() {
    let mut core = python("import sys; print(sys.stdin.readline().strip())")
        .spawn()
        .expect("spawn");
    let mut stdin = core.take_stdin().expect("stdin");
    stdin.write_all(b"ping\n").await.expect("write");
    stdin.flush().await.expect("flush");
    drop(stdin);
    let stdout = core.take_stdout().expect("stdout");
    assert_eq!(read_first_line(stdout).await, "ping");
    core.shutdown().await.expect("shutdown");
}
