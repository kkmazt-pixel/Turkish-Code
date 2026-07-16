//! Real-process composition tests: bootstrap wires the whole runtime — the
//! Core, the permission bridge (answering a Ç→K request), and the event
//! forwarder (delivering a notification to the sink) — and restart re-wires it.

use super::*;
use std::sync::{Arc, Mutex};

use serde_json::{json, Value};

use crate::core_process::CoreSpec;
use crate::events::EventSink;
use crate::permissions::{PermissionMode, PolicyResponder};

/// An [`EventSink`] recording every emitted event, cloneable for inspection.
#[derive(Clone, Default)]
struct CollectingSink {
    events: Arc<Mutex<Vec<(String, Value)>>>,
}

impl EventSink for CollectingSink {
    fn emit(&self, name: &str, payload: &Value) {
        self.events
            .lock()
            .expect("sink mutex")
            .push((name.to_owned(), payload.clone()));
    }
}

impl CollectingSink {
    fn names(&self) -> Vec<String> {
        self.events
            .lock()
            .expect("sink mutex")
            .iter()
            .map(|(name, _)| name.clone())
            .collect()
    }

    fn payload_for(&self, name: &str) -> Option<Value> {
        self.events
            .lock()
            .expect("sink mutex")
            .iter()
            .find(|(event, _)| event == name)
            .map(|(_, payload)| payload.clone())
    }
}

/// A Python "Core" that health-answers, echoes, and on `provoke` issues a Ç→K
/// `permission.request`, then emits the shell's decision as a notification.
const APP_CORE: &str = r#"
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
def readm():
    h = rex(4)
    if h is None:
        return None
    (l,) = struct.unpack('>I', h)
    p = rex(l)
    return None if p is None else json.loads(p.decode())
while True:
    m = readm()
    if m is None:
        break
    method, mid = m.get('method'), m.get('id')
    if method == 'app.shutdown':
        snd({'jsonrpc':'2.0','id':mid,'result':{'acknowledged':True}}); break
    elif method == 'app.health':
        snd({'jsonrpc':'2.0','id':mid,'result':{'status':'ok'}})
    elif method == 'provoke':
        snd({'jsonrpc':'2.0','id':'q1','method':'permission.request','params':{'capability':'dialog','reason':'x'}})
        resp = readm()
        decision = resp['result']['decision'] if resp and 'result' in resp else 'none'
        snd({'jsonrpc':'2.0','method':'decided','params':{'decision':decision}})
        if mid is not None:
            snd({'jsonrpc':'2.0','id':mid,'result':{'ok':True}})
    elif mid is not None:
        snd({'jsonrpc':'2.0','id':mid,'result':{'echo':m.get('params')}})
"#;

fn app(sink: CollectingSink) -> DesktopApp<PolicyResponder, CollectingSink> {
    let spec = CoreSpec::new("python3").arg("-c").arg(APP_CORE);
    DesktopApp::new(
        spec,
        LifecycleConfig::default(),
        PolicyResponder::new(PermissionMode::Auto),
        sink,
    )
}

async fn wait_for_event(sink: &CollectingSink, name: &str) {
    for _ in 0..100 {
        if sink.names().iter().any(|event| event == name) {
            return;
        }
        tokio::time::sleep(std::time::Duration::from_millis(10)).await;
    }
    panic!("event '{name}' never arrived");
}

#[tokio::test]
async fn bootstrap_wires_permissions_and_events() {
    let sink = CollectingSink::default();
    let app = app(sink.clone());

    app.bootstrap().await.expect("bootstrap");
    assert_eq!(app.status().await, CoreStatus::Running);
    assert_eq!(app.health().await.expect("health")["status"], "ok");

    // provoke -> Core asks permission (bridge answers) -> Core emits `decided`.
    app.request("provoke", None).await.expect("provoke");
    wait_for_event(&sink, "decided").await;
    assert_eq!(
        sink.payload_for("decided"),
        Some(json!({"decision": "allow"}))
    );

    app.shutdown().await.expect("shutdown");
    assert_eq!(app.status().await, CoreStatus::Stopped);
}

#[tokio::test]
async fn plain_requests_are_forwarded() {
    let app = app(CollectingSink::default());
    app.bootstrap().await.expect("bootstrap");
    match app
        .request("echo", Some(json!({"v": 7})))
        .await
        .expect("echo")
    {
        Response::Success(result) => assert_eq!(result, json!({"echo": {"v": 7}})),
        Response::Error(err) => panic!("unexpected error: {}", err.message),
    }
    app.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn restart_rewires_the_bridge() {
    let sink = CollectingSink::default();
    let app = app(sink.clone());
    app.bootstrap().await.expect("bootstrap");

    app.restart().await.expect("restart");
    assert_eq!(app.status().await, CoreStatus::Running);

    // The re-attached bridge still services the fresh Core's permission requests.
    app.request("provoke", None).await.expect("provoke");
    wait_for_event(&sink, "decided").await;
    assert_eq!(
        sink.payload_for("decided"),
        Some(json!({"decision": "allow"}))
    );

    app.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn shutdown_without_bootstrap_is_clean() {
    let app = app(CollectingSink::default());
    app.shutdown().await.expect("shutdown");
    assert_eq!(app.status().await, CoreStatus::Stopped);
}
