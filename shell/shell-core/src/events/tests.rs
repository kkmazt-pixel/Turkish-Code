//! Unit tests for the event forwarder plus a real-process re-emission test.

use super::*;
use std::sync::{Arc, Mutex};

use serde_json::json;
use tokio::sync::mpsc;

use crate::core_process::CoreSpec;
use crate::ipc::CoreChannel;

/// An [`EventSink`] that records every emitted `(name, payload)` pair.
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
    fn snapshot(&self) -> Vec<(String, Value)> {
        self.events.lock().expect("sink mutex").clone()
    }
}

#[tokio::test]
async fn forwards_every_notification_in_order() {
    let (tx, rx) = mpsc::unbounded_channel();
    tx.send(Notification::new("token.delta", Some(json!({"t": "a"}))))
        .unwrap();
    tx.send(Notification::new("token.delta", Some(json!({"t": "b"}))))
        .unwrap();
    drop(tx); // ends the stream so the forwarder returns

    let sink = CollectingSink::default();
    forward_events(sink.clone(), rx).await;

    assert_eq!(
        sink.snapshot(),
        vec![
            ("token.delta".to_owned(), json!({"t": "a"})),
            ("token.delta".to_owned(), json!({"t": "b"})),
        ]
    );
}

#[tokio::test]
async fn a_notification_without_params_emits_null() {
    let (tx, rx) = mpsc::unbounded_channel();
    tx.send(Notification::new("health.change", None)).unwrap();
    drop(tx);

    let sink = CollectingSink::default();
    forward_events(sink.clone(), rx).await;

    assert_eq!(
        sink.snapshot(),
        vec![("health.change".to_owned(), Value::Null)]
    );
}

/// A Python "Core" that, on `emit`, answers then pushes an `evt` notification.
const EMITTER_CORE: &str = r#"
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
    elif method == 'emit':
        snd({'jsonrpc':'2.0','id':mid,'result':{'ok':True}})
        snd({'jsonrpc':'2.0','method':'evt','params':{'k':1}})
"#;

#[tokio::test]
async fn forwards_real_core_notifications_to_the_sink() {
    let mut core = CoreSpec::new("python3")
        .arg("-c")
        .arg(EMITTER_CORE)
        .spawn()
        .expect("spawn emitter core");
    let stdout = core.take_stdout().expect("stdout");
    let stdin = core.take_stdin().expect("stdin");
    let (channel, events) = CoreChannel::new(stdout, stdin);

    let sink = CollectingSink::default();
    let forwarder = tokio::spawn(forward_events(sink.clone(), events.notifications));

    channel.request("emit", None).await.expect("emit request");

    // Wait for the forwarded event to land.
    let mut saw_event = false;
    for _ in 0..100 {
        if sink.snapshot().iter().any(|(name, _)| name == "evt") {
            saw_event = true;
            break;
        }
        tokio::time::sleep(std::time::Duration::from_millis(10)).await;
    }
    assert!(saw_event, "the core notification was not forwarded");
    assert_eq!(sink.snapshot().last().unwrap().1, json!({"k": 1}));

    let _ = channel.request("app.shutdown", None).await;
    drop(channel);
    core.wait().await.expect("core exits");
    forwarder.abort();
}
