//! Integration: the composed `DesktopApp` end-to-end over a real child Core —
//! bootstrap, parallel requests, restart re-wiring, and the permission bridge
//! denying/allowing a Core→shell request.

mod common;

use serde_json::json;
use shell_core::{Capability, CoreStatus, PermissionMode, PolicyResponder, Response};

use common::{desktop, wait_for_event, CollectingSink};

#[tokio::test]
async fn bootstrap_and_shutdown_the_whole_app() {
    let app = desktop(
        PolicyResponder::new(PermissionMode::Auto),
        CollectingSink::default(),
    );
    app.bootstrap().await.expect("bootstrap");
    assert_eq!(app.status().await, CoreStatus::Running);
    app.shutdown().await.expect("shutdown");
    assert_eq!(app.status().await, CoreStatus::Stopped);
}

#[tokio::test]
async fn parallel_requests_all_correlate() {
    let app = desktop(
        PolicyResponder::new(PermissionMode::Auto),
        CollectingSink::default(),
    );
    app.bootstrap().await.expect("bootstrap");

    let (a, b, c, d) = tokio::join!(
        app.request("echo", Some(json!({"n": 0}))),
        app.request("echo", Some(json!({"n": 1}))),
        app.request("echo", Some(json!({"n": 2}))),
        app.request("echo", Some(json!({"n": 3}))),
    );
    for (index, response) in [a, b, c, d].into_iter().enumerate() {
        match response.expect("request") {
            Response::Success(result) => assert_eq!(result["echo"]["n"], json!(index)),
            Response::Error(err) => panic!("unexpected error: {}", err.message),
        }
    }
    app.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn restart_yields_a_working_core() {
    let app = desktop(
        PolicyResponder::new(PermissionMode::Auto),
        CollectingSink::default(),
    );
    app.bootstrap().await.expect("bootstrap");
    app.restart().await.expect("restart");
    assert_eq!(app.status().await, CoreStatus::Running);

    match app
        .request("echo", Some(json!({"v": 1})))
        .await
        .expect("request")
    {
        Response::Success(result) => assert_eq!(result, json!({"echo": {"v": 1}})),
        Response::Error(err) => panic!("unexpected error: {}", err.message),
    }
    app.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn a_sensitive_permission_is_denied() {
    let sink = CollectingSink::default();
    // Ask mode + no grant + a sensitive capability => fail-safe deny.
    let app = desktop(PolicyResponder::new(PermissionMode::Ask), sink.clone());
    app.bootstrap().await.expect("bootstrap");

    app.request("provoke", Some(json!({"capability": "clipboard"})))
        .await
        .expect("provoke");
    wait_for_event(&sink, "decided").await;
    assert_eq!(
        sink.payload_for("decided"),
        Some(json!({"decision": "deny"}))
    );

    app.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn a_granted_permission_is_allowed() {
    let sink = CollectingSink::default();
    let responder = PolicyResponder::new(PermissionMode::Auto).with_grant(Capability::Clipboard);
    let app = desktop(responder, sink.clone());
    app.bootstrap().await.expect("bootstrap");

    app.request("provoke", Some(json!({"capability": "clipboard"})))
        .await
        .expect("provoke");
    wait_for_event(&sink, "decided").await;
    assert_eq!(
        sink.payload_for("decided"),
        Some(json!({"decision": "allow"}))
    );

    app.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn core_notifications_reach_the_sink() {
    let sink = CollectingSink::default();
    let app = desktop(PolicyResponder::new(PermissionMode::Auto), sink.clone());
    app.bootstrap().await.expect("bootstrap");

    app.request("emit", None).await.expect("emit");
    wait_for_event(&sink, "token.delta").await;
    assert_eq!(sink.payload_for("token.delta"), Some(json!({"text": "hi"})));

    app.shutdown().await.expect("shutdown");
}
