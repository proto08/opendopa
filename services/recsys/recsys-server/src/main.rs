use std::{io::IsTerminal, net::SocketAddr, sync::Arc};

use recsys_core::config::Config;
use recsys_server::{AppState, loader::PgLoader};
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() {
    // 端末に出すときは読みやすい形式、そうでなければ(Container Apps など)1行1JSON。Log Analytics で項目を引ける
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into());
    if std::io::stdout().is_terminal() {
        tracing_subscriber::fmt().with_env_filter(filter).init();
    } else {
        tracing_subscriber::fmt()
            .json()
            .with_env_filter(filter)
            .init();
    }

    // 待ち受けるポートは環境変数 PORT(既定 8080。ADR-0012 A15)
    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8080);
    // 内部 API の認証トークン。ないまま起動すると誰でも叩けるので、起動を止める
    let token = std::env::var("INTERNAL_TOKEN").unwrap_or_default();
    assert!(!token.is_empty(), "INTERNAL_TOKEN is not set");
    // 索引を読む読み取り専用ロールの接続文字列(Next.js の DATABASE_URL とは別)
    let db_url = std::env::var("RECSYS_DATABASE_URL").unwrap_or_default();
    assert!(!db_url.is_empty(), "RECSYS_DATABASE_URL is not set");
    // 係数。RECSYS_CONFIG があればそのファイル、なければ既定値(設計書 §7.1)
    let config = match std::env::var("RECSYS_CONFIG") {
        Ok(path) => {
            Config::from_file(&path).unwrap_or_else(|e| panic!("RECSYS_CONFIG ({path}): {e}"))
        }
        Err(_) => Config::default(),
    };

    let loader = PgLoader::new(&db_url).expect("RECSYS_DATABASE_URL");
    let state = AppState::new(Arc::new(loader), config);
    // 読み込みに失敗しても HTTP は先に起動する(/healthz は読み込めるまで 503)
    tokio::spawn({
        let state = state.clone();
        async move { state.load_with_retry().await }
    });

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    let listener = tokio::net::TcpListener::bind(addr).await.expect("bind");
    tracing::info!(%addr, "recsys listening");
    axum::serve(listener, recsys_server::app(token, state))
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await
        .expect("server");
}
