//! Shared harness for the Phase 12 integration suite.
//!
//! Every test drives a **real** child process that speaks the exact Core Channel
//! framing — only the Core's business logic is scripted (the shell neither knows
//! nor cares what a method computes). The real `python -m turkish_code` Core is
//! not used here: it currently fails to launch on this machine due to a
//! pre-existing Phase-2 bug (`guard_stdout` runs before `open_stdio_streams`,
//! leaving `sys.stdout` without a `fileno`), which is a Core-tier issue outside
//! the Desktop Shell's scope.

#![allow(dead_code)] // each integration binary uses a different subset

use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde_json::Value;
use shell_core::{
    CoreLifecycle, CoreSpec, DesktopApp, EventSink, LifecycleConfig, PermissionResponder,
};

/// A real child "Core" covering every scenario the suite exercises: health,
/// shutdown, echo, notification (`emit`), a stall (`slow`), an unexpected exit
/// (`crash`), and a Core→shell permission ask (`provoke`).
pub const INTEG_CORE: &str = r#"
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
    params = m.get('params') or {}
    if method == 'app.shutdown':
        snd({'jsonrpc':'2.0','id':mid,'result':{'acknowledged':True}}); break
    elif method == 'app.health':
        snd({'jsonrpc':'2.0','id':mid,'result':{'status':'ok'}})
    elif method == 'emit':
        snd({'jsonrpc':'2.0','id':mid,'result':{'ok':True}})
        snd({'jsonrpc':'2.0','method':'token.delta','params':{'text':'hi'}})
    elif method == 'slow':
        import time; time.sleep(2); snd({'jsonrpc':'2.0','id':mid,'result':{'late':True}})
    elif method == 'crash':
        sys.exit(1)
    elif method == 'provoke':
        cap = params.get('capability', 'dialog')
        snd({'jsonrpc':'2.0','id':'q1','method':'permission.request','params':{'capability':cap,'reason':'x'}})
        resp = readm()
        decision = resp['result']['decision'] if resp and 'result' in resp else 'none'
        snd({'jsonrpc':'2.0','method':'decided','params':{'decision':decision}})
        if mid is not None:
            snd({'jsonrpc':'2.0','id':mid,'result':{'ok':True}})
    elif mid is not None:
        snd({'jsonrpc':'2.0','id':mid,'result':{'echo':params}})
"#;

/// A launch spec for the integration Core.
pub fn spec() -> CoreSpec {
    CoreSpec::new("python3").arg("-c").arg(INTEG_CORE)
}

/// A fresh supervisor over the integration Core.
pub fn lifecycle() -> CoreLifecycle {
    CoreLifecycle::new(spec(), LifecycleConfig::default())
}

/// A composed desktop app over the integration Core with the given responder.
pub fn desktop<R>(responder: R, sink: CollectingSink) -> DesktopApp<R, CollectingSink>
where
    R: PermissionResponder + Send + Sync + 'static,
{
    DesktopApp::new(spec(), LifecycleConfig::default(), responder, sink)
}

/// An [`EventSink`] recording every emitted event; cloneable for inspection.
#[derive(Clone, Default)]
pub struct CollectingSink {
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
    pub fn names(&self) -> Vec<String> {
        self.events
            .lock()
            .expect("sink mutex")
            .iter()
            .map(|(name, _)| name.clone())
            .collect()
    }

    pub fn payload_for(&self, name: &str) -> Option<Value> {
        self.events
            .lock()
            .expect("sink mutex")
            .iter()
            .find(|(event, _)| event == name)
            .map(|(_, payload)| payload.clone())
    }
}

/// Poll until `name` has been emitted onto `sink`, or panic after ~1s.
pub async fn wait_for_event(sink: &CollectingSink, name: &str) {
    for _ in 0..100 {
        if sink.names().iter().any(|event| event == name) {
            return;
        }
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
    panic!("event '{name}' never arrived");
}
