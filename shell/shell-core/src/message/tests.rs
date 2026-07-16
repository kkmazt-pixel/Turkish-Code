//! Unit tests for [`super`] — wire shapes and classification vs. the Core.

use super::*;
use serde_json::json;

#[test]
fn request_to_wire_matches_the_core_envelope() {
    let req = Request::new("kabuk-1", "app.health", Some(json!({"x": 1})));
    assert_eq!(
        req.to_wire(),
        json!({"jsonrpc": "2.0", "id": "kabuk-1", "method": "app.health", "params": {"x": 1}})
    );
}

#[test]
fn request_omits_absent_params_and_meta() {
    let req = Request::new("kabuk-2", "app.shutdown", None);
    assert_eq!(
        req.to_wire(),
        json!({"jsonrpc": "2.0", "id": "kabuk-2", "method": "app.shutdown"})
    );
}

#[test]
fn notification_has_no_id() {
    let note = Notification::new("token.delta", Some(json!({"text": "hi"})));
    let wire = note.to_wire();
    assert!(wire.get("id").is_none());
    assert_eq!(wire["method"], json!("token.delta"));
}

#[test]
fn parses_a_success_response() {
    let payload = to_bytes(&json!({"jsonrpc": "2.0", "id": "kabuk-1", "result": {"ok": true}}));
    match parse(&payload).expect("parse") {
        Incoming::Response {
            id,
            body: Response::Success(result),
        } => {
            assert_eq!(id_key(&id), "kabuk-1");
            assert_eq!(result, json!({"ok": true}));
        }
        other => panic!("expected success response, got {other:?}"),
    }
}

#[test]
fn parses_an_error_response() {
    let payload = to_bytes(&json!({
        "jsonrpc": "2.0", "id": "kabuk-1",
        "error": {"code": -32000, "message": "boom", "data": {"kind": "internal"}}
    }));
    match parse(&payload).expect("parse") {
        Incoming::Response {
            body: Response::Error(err),
            ..
        } => {
            assert_eq!(err.code, -32000);
            assert_eq!(err.message, "boom");
            assert_eq!(err.data, Some(json!({"kind": "internal"})));
        }
        other => panic!("expected error response, got {other:?}"),
    }
}

#[test]
fn parses_a_notification_and_an_inbound_request() {
    let note = to_bytes(&json!({"jsonrpc": "2.0", "method": "health.change"}));
    assert!(matches!(
        parse(&note).expect("parse note"),
        Incoming::Notification(_)
    ));

    let req = to_bytes(&json!({"jsonrpc": "2.0", "id": "core-1", "method": "tool.invoke"}));
    assert!(matches!(
        parse(&req).expect("parse req"),
        Incoming::Request(_)
    ));
}

#[test]
fn rejects_wrong_jsonrpc_version() {
    let payload = to_bytes(&json!({"jsonrpc": "1.0", "method": "x"}));
    assert_eq!(parse(&payload).expect_err("reject").kind(), "ipc");
}

#[test]
fn rejects_unknown_shape_and_non_object() {
    let unknown = to_bytes(&json!({"jsonrpc": "2.0"}));
    assert_eq!(parse(&unknown).expect_err("reject").kind(), "ipc");
    let not_object = to_bytes(&json!([1, 2, 3]));
    assert_eq!(parse(&not_object).expect_err("reject").kind(), "ipc");
}
