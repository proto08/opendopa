use std::net::SocketAddr;

use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .init();

    // 待ち受けるポートは環境変数 PORT(既定 8080。ADR-0012 A15)
    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8080);
    // 内部 API の認証トークン。ないまま起動すると誰でも叩けるので、起動を止める
    let token = std::env::var("INTERNAL_TOKEN").unwrap_or_default();
    assert!(!token.is_empty(), "INTERNAL_TOKEN is not set");
    let addr = SocketAddr::from(([0, 0, 0, 0], port));

    let listener = tokio::net::TcpListener::bind(addr).await.expect("bind");
    tracing::info!(%addr, "recsys listening");
    axum::serve(listener, recsys_server::app(token))
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await
        .expect("server");
}
