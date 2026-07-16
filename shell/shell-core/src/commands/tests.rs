//! Real-process tests for the command surface against a supervised `python3` Core.

use super::*;
use serde_json::json;

use crate::core_process::CoreSpec;
use crate::lifecycle::LifecycleConfig;

/// A Python "Core" answering `app.health`/`app.shutdown` and echoing others.
const COMMAND_CORE: &str = r#"
import sys, struct, json
r, w = sys.stdin.buffer, sys.stdout.buffer
def rex(n):
    b = b''
    while len(b) < n:
        c = r.read(n - len(b))
        if not c:
            return None
        b += c
    return b
def snd(o):
    d = json.dumps(o).encode(); w.write(struct.pack('>I', len(d)) + d); w.flush()
while True:
    h = rex(4)
    if h is None:
        break
    (l,) = struct.unpack('>I', h)
    p = rex(l)
    if p is None:
        break
    m = json.loads(p.decode()); method, mid = m.get('method'), m.get('id')
    if method == 'app.shutdown':
        snd({'jsonrpc':'2.0','id':mid,'result':{'acknowledged':True}}); break
    elif method == 'app.health':
        snd({'jsonrpc':'2.0','id':mid,'result':{'status':'ok'}})
    elif mid is not None:
        snd({'jsonrpc':'2.0','id':mid,'result':{'echo':m.get('params')}})
"#;

fn api() -> ShellApi {
    let spec = CoreSpec::new("python3").arg("-c").arg(COMMAND_CORE);
    ShellApi::new(CoreLifecycle::new(spec, LifecycleConfig::default()))
}

#[tokio::test]
async fn bootstrap_status_and_shutdown() {
    let api = api();
    assert_eq!(api.status().await, CoreStatus::Stopped);
    api.bootstrap().await.expect("bootstrap");
    assert_eq!(api.status().await, CoreStatus::Running);

    let health = api.health().await.expect("health");
    assert_eq!(health["status"], "ok");

    api.shutdown().await.expect("shutdown");
    assert_eq!(api.status().await, CoreStatus::Stopped);
}

#[tokio::test]
async fn request_forwards_to_the_core() {
    let api = api();
    api.bootstrap().await.expect("bootstrap");
    match api
        .request("echo", Some(json!({"a": 1})))
        .await
        .expect("request")
    {
        Response::Success(result) => assert_eq!(result, json!({"echo": {"a": 1}})),
        Response::Error(err) => panic!("unexpected error: {}", err.message),
    }
    api.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn requests_run_concurrently() {
    let api = api();
    api.bootstrap().await.expect("bootstrap");
    let (a, b, c) = tokio::join!(
        api.request("echo", Some(json!({"n": 1}))),
        api.request("echo", Some(json!({"n": 2}))),
        api.request("echo", Some(json!({"n": 3}))),
    );
    for (index, response) in [a, b, c].into_iter().enumerate() {
        match response.expect("request") {
            Response::Success(result) => {
                assert_eq!(result["echo"]["n"], json!(index + 1));
            }
            Response::Error(err) => panic!("unexpected error: {}", err.message),
        }
    }
    api.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn restart_through_the_api() {
    let api = api();
    api.bootstrap().await.expect("bootstrap");
    api.restart().await.expect("restart");
    assert_eq!(api.status().await, CoreStatus::Running);
    api.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn request_without_a_running_core_fails() {
    let api = api();
    let err = api.request("echo", None).await.expect_err("no core");
    assert_eq!(err.kind(), "process");
}

#[tokio::test]
async fn clones_share_the_same_core() {
    let api = api();
    let clone = api.clone();
    api.bootstrap().await.expect("bootstrap");
    assert_eq!(clone.status().await, CoreStatus::Running);
    clone.shutdown().await.expect("shutdown");
    assert_eq!(api.status().await, CoreStatus::Stopped);
}
