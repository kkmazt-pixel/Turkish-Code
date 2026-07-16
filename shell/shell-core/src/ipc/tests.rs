//! Unit tests for [`super`] — a real Python child speaking the exact frame
//! protocol (minimal mocking): request/response correlation, heartbeat,
//! notifications, concurrency, timeout, and channel-close behaviour.

use super::*;
use crate::core_process::{CoreProcess, CoreSpec};
use serde_json::json;

/// An inline Python "Core" that speaks the exact frame protocol: it echoes
/// requests, answers `app.health`, can emit a notification, error, or stall.
const ECHO_CORE: &str = r#"
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
    if method == 'app.shutdown':
        send({'jsonrpc':'2.0','id':mid,'result':{'acknowledged':True}}); break
    elif method == 'app.health':
        send({'jsonrpc':'2.0','id':mid,'result':{'status':'ok'}})
    elif method == 'emit':
        send({'jsonrpc':'2.0','id':mid,'result':{'ok':True}})
        send({'jsonrpc':'2.0','method':'token.delta','params':{'text':'hi'}})
    elif method == 'boom':
        send({'jsonrpc':'2.0','id':mid,'error':{'code':-32000,'message':'kaboom','data':{'kind':'internal'}}})
    elif method == 'slow':
        import time; time.sleep(2); send({'jsonrpc':'2.0','id':mid,'result':{'late':True}})
    elif mid is not None:
        send({'jsonrpc':'2.0','id':mid,'result':{'echo':msg.get('params')}})
"#;

fn spawn_echo_core() -> (CoreProcess, CoreChannel, CoreEvents) {
    let mut core = CoreSpec::new("python3")
        .arg("-c")
        .arg(ECHO_CORE)
        .spawn()
        .expect("spawn echo core");
    let stdout = core.take_stdout().expect("stdout");
    let stdin = core.take_stdin().expect("stdin");
    let (channel, events) = CoreChannel::new(stdout, stdin);
    (core, channel, events)
}

/// Cleanly stop the echo core via the real `app.shutdown` request, then reap.
async fn stop(mut core: CoreProcess, channel: CoreChannel) {
    let _ = channel.request("app.shutdown", None).await;
    drop(channel);
    core.wait().await.expect("core exits");
}

#[tokio::test]
async fn request_correlates_its_response() {
    let (core, channel, _events) = spawn_echo_core();
    let response = channel
        .request("echo.me", Some(json!({"x": 1})))
        .await
        .expect("request");
    match response {
        Response::Success(result) => assert_eq!(result, json!({"echo": {"x": 1}})),
        Response::Error(err) => panic!("unexpected error: {}", err.message),
    }
    stop(core, channel).await;
}

#[tokio::test]
async fn heartbeat_returns_health() {
    let (core, channel, _events) = spawn_echo_core();
    let health = channel
        .heartbeat(Duration::from_secs(5))
        .await
        .expect("heartbeat");
    assert_eq!(health, json!({"status": "ok"}));
    stop(core, channel).await;
}

#[tokio::test]
async fn error_response_surfaces_as_response_error() {
    let (core, channel, _events) = spawn_echo_core();
    match channel.request("boom", None).await.expect("request") {
        Response::Error(err) => {
            assert_eq!(err.code, -32000);
            assert_eq!(err.message, "kaboom");
        }
        Response::Success(_) => panic!("expected an error response"),
    }
    stop(core, channel).await;
}

#[tokio::test]
async fn notifications_reach_the_events_stream() {
    let (core, channel, mut events) = spawn_echo_core();
    channel.request("emit", None).await.expect("request");
    let note = events.notifications.recv().await.expect("a notification");
    assert_eq!(note.method, "token.delta");
    assert_eq!(note.params, Some(json!({"text": "hi"})));
    stop(core, channel).await;
}

#[tokio::test]
async fn concurrent_requests_correlate_independently() {
    let (core, channel, _events) = spawn_echo_core();
    // Four requests in flight at once; each must get its own echo back.
    let (a, b, c, d) = tokio::join!(
        channel.request("echo", Some(json!({"n": 0}))),
        channel.request("echo", Some(json!({"n": 1}))),
        channel.request("echo", Some(json!({"n": 2}))),
        channel.request("echo", Some(json!({"n": 3}))),
    );
    for (n, response) in [a, b, c, d].into_iter().enumerate() {
        match response.expect("request") {
            Response::Success(result) => assert_eq!(result, json!({"echo": {"n": n}})),
            Response::Error(err) => panic!("unexpected error: {}", err.message),
        }
    }
    stop(core, channel).await;
}

#[tokio::test]
async fn request_timeout_fires_when_core_stalls() {
    let (mut core, channel, _events) = spawn_echo_core();
    let err = channel
        .request_timeout("slow", None, Duration::from_millis(150))
        .await
        .expect_err("should time out");
    assert_eq!(err.kind(), "timeout");
    core.kill().await.expect("kill");
}

#[tokio::test]
async fn pending_request_unblocks_when_channel_closes() {
    let (mut core, channel, _events) = spawn_echo_core();
    core.kill().await.expect("kill"); // Core gone before we ask.
    let err = channel.request("echo", None).await.expect_err("closed");
    assert_eq!(err.kind(), "ipc");
}
