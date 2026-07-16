//! Integration: Core process + Channel + lifecycle, driven end-to-end over real
//! child processes — launch, shutdown, IPC request/notification, heartbeat,
//! timeout, and unexpected-crash recovery.

mod common;

use std::time::Duration;

use serde_json::json;
use shell_core::{CoreStatus, Response, PROTOCOL_VERSION};

use common::lifecycle;

#[test]
fn protocol_version_matches_the_core_channel_contract() {
    // The shell speaks the Phase-2 contract verbatim (doc 10 §13).
    assert_eq!(PROTOCOL_VERSION, "1.0.0");
}

#[tokio::test]
async fn core_launches_and_shuts_down() {
    let mut life = lifecycle();
    assert_eq!(life.status(), CoreStatus::Stopped);
    life.start().await.expect("launch");
    assert_eq!(life.status(), CoreStatus::Running);
    life.shutdown().await.expect("shutdown");
    assert_eq!(life.status(), CoreStatus::Stopped);
    assert!(life.channel().is_none());
}

#[tokio::test]
async fn ipc_request_round_trips() {
    let mut life = lifecycle();
    life.start().await.expect("launch");
    let channel = life.channel().expect("channel");
    match channel
        .request("echo", Some(json!({"x": 42})))
        .await
        .expect("request")
    {
        Response::Success(result) => assert_eq!(result, json!({"echo": {"x": 42}})),
        Response::Error(err) => panic!("unexpected error: {}", err.message),
    }
    life.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn ipc_notification_is_received() {
    let mut life = lifecycle();
    life.start().await.expect("launch");
    let channel = life.channel().expect("channel");
    let mut events = life.take_events().expect("events");

    channel.request("emit", None).await.expect("emit");
    let note = events.notifications.recv().await.expect("notification");
    assert_eq!(note.method, "token.delta");
    assert_eq!(note.params, Some(json!({"text": "hi"})));

    life.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn heartbeat_reports_health() {
    let mut life = lifecycle();
    life.start().await.expect("launch");
    let health = life.health_check().await.expect("heartbeat");
    assert_eq!(health["status"], "ok");
    life.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn a_slow_request_times_out() {
    let mut life = lifecycle();
    life.start().await.expect("launch");
    let channel = life.channel().expect("channel");
    let err = channel
        .request_timeout("slow", None, Duration::from_millis(150))
        .await
        .expect_err("should time out");
    assert_eq!(err.kind(), "timeout");
    life.shutdown().await.expect("shutdown");
}

#[tokio::test]
async fn an_unexpected_crash_is_detected_and_recovered() {
    let mut life = lifecycle();
    life.start().await.expect("launch");

    // Provoke an unexpected exit (no response).
    let channel = life.channel().expect("channel");
    let _ = channel.notify("crash", None).await;
    drop(channel);

    for _ in 0..100 {
        if life.has_exited().expect("poll") {
            break;
        }
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
    assert!(life.has_exited().expect("exited"));

    let recovered = life.recover_if_crashed().await.expect("recover");
    assert!(recovered);
    assert_eq!(life.status(), CoreStatus::Running);
    assert_eq!(life.restart_count(), 1);
    assert_eq!(life.health_check().await.expect("health")["status"], "ok");

    life.shutdown().await.expect("shutdown");
}
