//! Unit tests for [`super`] — real supervised `python3` Cores: start, health,
//! shutdown, crash detection + recovery, and the restart budget.

use super::*;
use crate::message::Response;

/// A supervisable "Core": answers `app.health`/`app.shutdown`, echoes, and can
/// crash on demand (`crash` → exit without responding).
const SUPERVISABLE_CORE: &str = r#"
import sys, struct, json
r, w = sys.stdin.buffer, sys.stdout.buffer
def read_exactly(n):
    buf = b''
    while len(buf) < n:
        chunk = r.read(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf
def send(obj):
    data = json.dumps(obj).encode('utf-8')
    w.write(struct.pack('>I', len(data)) + data); w.flush()
while True:
    header = read_exactly(4)
    if header is None:
        break
    (length,) = struct.unpack('>I', header)
    payload = read_exactly(length)
    if payload is None:
        break
    msg = json.loads(payload.decode('utf-8'))
    method, mid = msg.get('method'), msg.get('id')
    if method == 'crash':
        sys.exit(1)
    elif method == 'app.shutdown':
        send({'jsonrpc':'2.0','id':mid,'result':{'acknowledged':True}}); break
    elif method == 'app.health':
        send({'jsonrpc':'2.0','id':mid,'result':{'status':'ok'}})
    elif mid is not None:
        send({'jsonrpc':'2.0','id':mid,'result':{'echo':msg.get('params')}})
"#;

fn lifecycle(max_restarts: u32) -> CoreLifecycle {
    let spec = CoreSpec::new("python3").arg("-c").arg(SUPERVISABLE_CORE);
    CoreLifecycle::new(
        spec,
        LifecycleConfig {
            heartbeat_timeout: Duration::from_secs(5),
            max_restarts,
        },
    )
}

/// Poll until the current process has exited, so crash tests are not flaky.
async fn wait_until_exited(life: &mut CoreLifecycle) {
    for _ in 0..100 {
        if life.has_exited().expect("poll status") {
            return;
        }
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
    panic!("core did not exit in time");
}

#[tokio::test]
async fn start_brings_core_to_running_then_shutdown_stops_it() {
    let mut life = lifecycle(3);
    assert_eq!(life.status(), CoreStatus::Stopped);
    life.start().await.expect("start");
    assert_eq!(life.status(), CoreStatus::Running);

    let health = life.health_check().await.expect("health");
    assert_eq!(health["status"], "ok");

    life.shutdown().await.expect("shutdown");
    assert_eq!(life.status(), CoreStatus::Stopped);
    assert!(life.channel().is_none());
}

#[tokio::test]
async fn starting_twice_is_rejected() {
    let mut life = lifecycle(3);
    life.start().await.expect("start");
    let err = life.start().await.expect_err("second start");
    assert_eq!(err.kind(), "process");
    life.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn restart_replaces_the_process_and_counts() {
    let mut life = lifecycle(3);
    life.start().await.expect("start");
    life.restart().await.expect("restart");
    assert_eq!(life.status(), CoreStatus::Running);
    assert_eq!(life.restart_count(), 1);

    // The fresh channel works.
    match life.channel().expect("channel").request("echo", None).await {
        Ok(Response::Success(result)) => assert_eq!(result, serde_json::json!({"echo": null})),
        other => panic!("unexpected: {other:?}"),
    }
    life.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn health_check_fails_when_not_running() {
    let life = lifecycle(3);
    let err = life.health_check().await.expect_err("not running");
    assert_eq!(err.kind(), "process");
}

#[tokio::test]
async fn crash_is_detected_and_recovered() {
    let mut life = lifecycle(3);
    life.start().await.expect("start");

    // Make the Core exit unexpectedly (no response to this request).
    let _ = life.channel().expect("channel").notify("crash", None).await;
    wait_until_exited(&mut life).await;
    assert!(life.has_exited().expect("exited"));

    let recovered = life.recover_if_crashed().await.expect("recover");
    assert!(recovered);
    assert_eq!(life.status(), CoreStatus::Running);
    assert_eq!(life.restart_count(), 1);

    // Recovered Core answers again.
    let health = life.health_check().await.expect("health after recovery");
    assert_eq!(health["status"], "ok");
    life.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn recover_is_a_noop_when_core_is_healthy() {
    let mut life = lifecycle(3);
    life.start().await.expect("start");
    let recovered = life.recover_if_crashed().await.expect("recover");
    assert!(!recovered);
    assert_eq!(life.restart_count(), 0);
    life.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn restart_budget_is_enforced() {
    let mut life = lifecycle(1); // exactly one restart allowed
    life.start().await.expect("start");
    life.restart().await.expect("first restart");
    assert_eq!(life.restart_count(), 1);

    let err = life.restart().await.expect_err("budget exhausted");
    assert_eq!(err.kind(), "process");
    // The refusal left the Core running and untouched.
    assert_eq!(life.status(), CoreStatus::Running);
    life.shutdown().await.expect("shutdown");
}
