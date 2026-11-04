//! recsys の HTTP サーバー部分(ADR-0012 A6)。
//!
//! 内部 API(設計書 §6.6)と、起動時の DB の読み込みを担当する。計算は recsys-core に任せる。
//! #12 の段階では DB に接続せず、`/healthz` だけを返す(ADR-0012 A14)。

use axum::{Json, Router, routing::get};
use serde::Serialize;

#[derive(Serialize)]
struct Health {
    status: &'static str,
    /// 読み込んだ動画の索引の件数(M4a で DB から読み込むまでは 0)
    videos: usize,
}

async fn healthz() -> Json<Health> {
    Json(Health {
        status: "ok",
        videos: 0,
    })
}

pub fn app() -> Router {
    Router::new().route("/healthz", get(healthz))
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::Body, http::Request, http::StatusCode};
    use http_body_util::BodyExt;
    use tower::ServiceExt;

    #[tokio::test]
    async fn healthz_returns_ok() {
        let res = app()
            .oneshot(Request::get("/healthz").body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await.unwrap().to_bytes();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(json, serde_json::json!({"status": "ok", "videos": 0}));
    }
}
