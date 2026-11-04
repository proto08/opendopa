//! recsys の HTTP サーバー部分(ADR-0012 A6)。
//!
//! 内部 API(設計書 §6.6)と、起動時の DB の読み込みを担当する。計算は recsys-core に任せる。
//! DB には接続せず、`/healthz` と、認証つきの `/internal/ping` だけを返す(ADR-0012 A14、ADR-0013 A4)。

use axum::{
    Json, Router,
    extract::{Request, State},
    http::{StatusCode, header::HeaderName},
    middleware::{self, Next},
    response::Response,
    routing::get,
};
use serde::Serialize;

/// web からの内部 HTTP が付けるヘッダー(設計書 §6.6)。値は環境変数 INTERNAL_TOKEN。
const TOKEN_HEADER: HeaderName = HeaderName::from_static("x-internal-token");

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

/// `/internal/*` の認証。`X-Internal-Token` が一致しなければ 401 を返す。
async fn require_token(
    State(token): State<String>,
    req: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    let given = req.headers().get(&TOKEN_HEADER).map(|v| v.as_bytes());
    if given.is_some_and(|g| constant_time_eq(g, token.as_bytes())) {
        Ok(next.run(req).await)
    } else {
        Err(StatusCode::UNAUTHORIZED)
    }
}

/// 長さが同じなら、内容に関わらず同じ時間で比べる(トークンの推測対策)。
fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    a.len() == b.len() && a.iter().zip(b).fold(0, |acc, (x, y)| acc | (x ^ y)) == 0
}

/// 認証を通ったことだけを返す。web → recsys の内部 HTTP の疎通確認に使う。
async fn ping() -> Json<serde_json::Value> {
    Json(serde_json::json!({"status": "ok"}))
}

/// `internal_token` は INTERNAL_TOKEN の値。空でないこと(呼び出し側で確かめる)。
pub fn app(internal_token: String) -> Router {
    let internal =
        Router::new()
            .route("/internal/ping", get(ping))
            .layer(middleware::from_fn_with_state(
                internal_token,
                require_token,
            ));
    Router::new()
        .route("/healthz", get(healthz))
        .merge(internal)
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::Body, http::Request, http::StatusCode};
    use http_body_util::BodyExt;
    use tower::ServiceExt;

    fn test_app() -> Router {
        app("secret".into())
    }

    async fn status(req: Request<Body>) -> StatusCode {
        test_app().oneshot(req).await.unwrap().status()
    }

    #[tokio::test]
    async fn healthz_needs_no_token() {
        let res = test_app()
            .oneshot(Request::get("/healthz").body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(res.status(), StatusCode::OK);
        let body = res.into_body().collect().await.unwrap().to_bytes();
        let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(json, serde_json::json!({"status": "ok", "videos": 0}));
    }

    #[tokio::test]
    async fn internal_requires_token() {
        let req = |token: Option<&str>| {
            let mut b = Request::get("/internal/ping");
            if let Some(t) = token {
                b = b.header("X-Internal-Token", t);
            }
            b.body(Body::empty()).unwrap()
        };
        assert_eq!(status(req(None)).await, StatusCode::UNAUTHORIZED);
        assert_eq!(status(req(Some("wrong"))).await, StatusCode::UNAUTHORIZED);
        assert_eq!(status(req(Some("secre"))).await, StatusCode::UNAUTHORIZED);
        assert_eq!(status(req(Some("secret"))).await, StatusCode::OK);
    }
}
