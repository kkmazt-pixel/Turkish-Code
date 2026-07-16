//! Unit tests for the policy and real-process tests of the bridge: a Python
//! "Core" issues a `permission.request` (Ç→K) and reads the shell's decision.

use super::*;
use std::sync::Arc;

use crate::core_process::CoreSpec;
use crate::ipc::{CoreChannel, CoreEvents};

fn request(capability: Capability) -> PermissionRequest {
    PermissionRequest {
        capability,
        target: None,
        reason: None,
    }
}

// --- policy unit tests --------------------------------------------------------

#[test]
fn capability_parses_ids_and_flags_sensitivity() {
    assert_eq!(Capability::parse("fs.write"), Some(Capability::Filesystem));
    assert_eq!(Capability::parse("clipboard"), Some(Capability::Clipboard));
    assert_eq!(Capability::parse("dialog"), Some(Capability::Dialog));
    assert_eq!(Capability::parse("net.egress"), None);
    assert!(Capability::Filesystem.is_sensitive());
    assert!(Capability::Clipboard.is_sensitive());
    assert!(!Capability::Dialog.is_sensitive());
    assert!(!Capability::Notifications.is_sensitive());
}

#[test]
fn decision_wire_tokens() {
    assert_eq!(Decision::Allow.as_str(), "allow");
    assert_eq!(Decision::Deny.as_str(), "deny");
}

#[test]
fn auto_allows_benign_but_denies_sensitive() {
    let responder = PolicyResponder::new(PermissionMode::Auto);
    assert_eq!(
        responder.evaluate(&request(Capability::Dialog)),
        Decision::Allow
    );
    assert_eq!(
        responder.evaluate(&request(Capability::Notifications)),
        Decision::Allow
    );
    assert_eq!(
        responder.evaluate(&request(Capability::Clipboard)),
        Decision::Deny
    );
}

#[test]
fn a_standing_grant_allows_a_sensitive_capability() {
    let responder = PolicyResponder::new(PermissionMode::Auto).with_grant(Capability::Filesystem);
    assert_eq!(
        responder.evaluate(&request(Capability::Filesystem)),
        Decision::Allow
    );
}

#[test]
fn plan_mode_denies_everything_ungranted() {
    let responder = PolicyResponder::new(PermissionMode::Plan);
    assert_eq!(
        responder.evaluate(&request(Capability::Dialog)),
        Decision::Deny
    );
    assert_eq!(
        responder.evaluate(&request(Capability::Filesystem)),
        Decision::Deny
    );
}

#[test]
fn malformed_params_do_not_parse() {
    assert!(PermissionRequest::from_params(None).is_none());
    let no_cap = serde_json::json!({"reason": "x"});
    assert!(PermissionRequest::from_params(Some(&no_cap)).is_none());
    let bad_cap = serde_json::json!({"capability": "net.egress"});
    assert!(PermissionRequest::from_params(Some(&bad_cap)).is_none());
}

// --- real-process bridge tests ------------------------------------------------

/// A Python "Core" that sends one Core→shell request (`method`/`capability`),
/// reads the shell's answer, and reports the decision as a `decided`
/// notification.
const REQUESTER_CORE: &str = r#"
import sys, struct, json
method = sys.argv[1] if len(sys.argv) > 1 else 'permission.request'
cap = sys.argv[2] if len(sys.argv) > 2 else 'dialog'
r, w = sys.stdin.buffer, sys.stdout.buffer
def read_exactly(n):
    buf = b''
    while len(buf) < n:
        c = r.read(n - len(buf))
        if not c:
            return None
        buf += c
    return buf
def send(o):
    d = json.dumps(o).encode(); w.write(struct.pack('>I', len(d)) + d); w.flush()
def readm():
    h = read_exactly(4)
    if h is None:
        return None
    (l,) = struct.unpack('>I', h)
    p = read_exactly(l)
    return None if p is None else json.loads(p.decode())
params = {'capability': cap, 'reason': 'test'} if method == 'permission.request' else {}
send({'jsonrpc':'2.0','id':'p1','method':method,'params':params})
resp = readm()
if resp and 'result' in resp:
    decision = resp['result'].get('decision', '?')
elif resp and 'error' in resp:
    decision = 'error'
else:
    decision = 'none'
send({'jsonrpc':'2.0','method':'decided','params':{'decision':decision}})
while True:
    m = readm()
    if m is None:
        break
    if m.get('method') == 'app.shutdown':
        send({'jsonrpc':'2.0','id':m.get('id'),'result':{'acknowledged':True}}); break
"#;

/// Drive one Core→shell request through the bridge and return the Core's
/// observed decision token.
async fn run_bridge(method: &str, capability: &str, responder: PolicyResponder) -> String {
    let mut core = CoreSpec::new("python3")
        .arg("-c")
        .arg(REQUESTER_CORE)
        .arg(method)
        .arg(capability)
        .spawn()
        .expect("spawn requester core");
    let stdout = core.take_stdout().expect("stdout");
    let stdin = core.take_stdin().expect("stdin");
    let (channel, events) = CoreChannel::new(stdout, stdin);
    let channel = Arc::new(channel);
    let CoreEvents {
        mut notifications,
        requests,
    } = events;

    let bridge = PermissionBridge::new(Arc::clone(&channel), responder);
    let bridge_task = tokio::spawn(async move { bridge.run(requests).await });

    let note = notifications.recv().await.expect("decided notification");
    assert_eq!(note.method, "decided");
    let decision = note.params.expect("params")["decision"]
        .as_str()
        .expect("decision string")
        .to_owned();

    let _ = channel.request("app.shutdown", None).await;
    core.wait().await.expect("core exits");
    bridge_task.abort();
    decision
}

#[tokio::test]
async fn bridge_allows_a_benign_dialog() {
    let decision = run_bridge(
        "permission.request",
        "dialog",
        PolicyResponder::new(PermissionMode::Auto),
    )
    .await;
    assert_eq!(decision, "allow");
}

#[tokio::test]
async fn bridge_denies_sensitive_without_grant() {
    let decision = run_bridge(
        "permission.request",
        "clipboard",
        PolicyResponder::new(PermissionMode::Auto),
    )
    .await;
    assert_eq!(decision, "deny");
}

#[tokio::test]
async fn bridge_allows_sensitive_with_a_grant() {
    let responder = PolicyResponder::new(PermissionMode::Auto).with_grant(Capability::Clipboard);
    let decision = run_bridge("permission.request", "clipboard", responder).await;
    assert_eq!(decision, "allow");
}

#[tokio::test]
async fn bridge_denies_a_malformed_request() {
    let decision = run_bridge(
        "permission.request",
        "net.egress",
        PolicyResponder::new(PermissionMode::Auto),
    )
    .await;
    assert_eq!(decision, "deny");
}

#[tokio::test]
async fn bridge_errors_on_an_unknown_method() {
    let decision = run_bridge(
        "tool.invoke",
        "dialog",
        PolicyResponder::new(PermissionMode::Auto),
    )
    .await;
    assert_eq!(decision, "error");
}
