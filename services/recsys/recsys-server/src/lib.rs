//! recsys の HTTP サーバー部分(ADR-0012 A6、ADR-0041)。
//!
//! 内部 API(設計書 §6.6)と、起動時・`reload` のときの DB の読み込みを担当する。計算は recsys-core に任せる。
//! 状態を持たず、DB には書き込まない。持つのは読み込んだ索引だけ。

pub mod loader;

use std::{
    sync::{
        Arc, RwLock,
        atomic::{AtomicU64, Ordering},
    },
    time::Duration,
};

use axum::{
    Json, Router,
    body::Bytes,
    extract::{Request, State},
    http::{StatusCode, header::HeaderName},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::{get, post},
};
use recsys_core::{
    config::Config,
    panel::{self, Taste},
    pick::{self, MAX_COUNT, Pick},
    rng::Rng,
    taste::{self, Event},
};
use serde::{Deserialize, Serialize};

use loader::{LoadError, Loader, Snapshot};

/// web からの内部 HTTP が付けるヘッダー(設計書 §6.6)。値は環境変数 INTERNAL_TOKEN。
const TOKEN_HEADER: HeaderName = HeaderName::from_static("x-internal-token");

/// サーバーが共有する状態。索引は `reload` のときに丸ごと入れ替える。
pub struct AppState {
    loader: Arc<dyn Loader>,
    config: Config,
    /// `None` は、まだ一度も読み込めていない。読むときは `Arc` を複製するだけで、すぐ手放す。
    snapshot: RwLock<Option<Arc<Snapshot>>>,
    seed: AtomicU64,
}

impl AppState {
    pub fn new(loader: Arc<dyn Loader>, config: Config) -> Arc<Self> {
        Arc::new(Self {
            loader,
            config,
            snapshot: RwLock::new(None),
            seed: AtomicU64::new(clock_seed()),
        })
    }

    fn current(&self) -> Option<Arc<Snapshot>> {
        self.snapshot
            .read()
            .unwrap_or_else(|e| e.into_inner())
            .clone()
    }

    /// 新しい索引を作ってから入れ替える。読み込み中も、動作中のリクエストは古い索引で答える。
    /// 失敗したときは、古い索引を残す。
    pub async fn reload(&self) -> Result<usize, LoadError> {
        let snap = Arc::new(self.loader.load().await?);
        let n = snap.index.len();
        *self.snapshot.write().unwrap_or_else(|e| e.into_inner()) = Some(snap);
        Ok(n)
    }

    /// 起動時の読み込み。失敗したら、間隔を延ばしながら(最大 30 秒)成功するまで再試行する。
    /// その間も HTTP は受け付け、`/healthz` と `/internal/feed|taste` は 503 を返す。
    pub async fn load_with_retry(&self) {
        let mut wait = Duration::from_secs(1);
        loop {
            match self.reload().await {
                Ok(n) => {
                    tracing::info!(videos = n, "索引を読み込んだ");
                    return;
                }
                Err(e) => {
                    tracing::warn!(error = %e, retry_in = ?wait, "索引の読み込みに失敗");
                    tokio::time::sleep(wait).await;
                    wait = (wait * 2).min(Duration::from_secs(30));
                }
            }
        }
    }

    /// リクエストごとに違う乱数を使う(暗号用途ではない)。
    fn rng(&self) -> Rng {
        Rng::new(
            self.seed
                .fetch_add(0x9E37_79B9_7F4A_7C15, Ordering::Relaxed),
        )
    }
}

fn clock_seed() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos() as u64)
        .unwrap_or(0)
}

/// `{ "error": "message" }` で返すエラー。
struct ApiError(StatusCode, String);

impl ApiError {
    fn bad_request(msg: impl Into<String>) -> Self {
        Self(StatusCode::BAD_REQUEST, msg.into())
    }

    fn unavailable(msg: impl Into<String>) -> Self {
        Self(StatusCode::SERVICE_UNAVAILABLE, msg.into())
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (self.0, Json(serde_json::json!({"error": self.1}))).into_response()
    }
}

fn parse_body<T: serde::de::DeserializeOwned>(body: &Bytes) -> Result<T, ApiError> {
    serde_json::from_slice(body)
        .map_err(|e| ApiError::bad_request(format!("リクエストが不正: {e}")))
}

/// 索引が読み込み済みで空でないスナップショット。
fn ready(state: &AppState) -> Result<Arc<Snapshot>, ApiError> {
    match state.current() {
        None => Err(ApiError::unavailable("索引を読み込み中")),
        Some(s) if s.index.is_empty() => Err(ApiError::unavailable("動画の索引が空")),
        Some(s) => Ok(s),
    }
}

#[derive(Serialize)]
struct Health {
    status: &'static str,
    /// 読み込んだ動画の索引の件数
    videos: usize,
}

async fn healthz(State(state): State<Arc<AppState>>) -> Response {
    match state.current() {
        Some(s) => Json(Health {
            status: "ok",
            videos: s.index.len(),
        })
        .into_response(),
        None => ApiError::unavailable("索引を読み込み中").into_response(),
    }
}

/// `/internal/*` の認証。`X-Internal-Token` が一致しなければ 401 を返す。
async fn require_token(
    State(token): State<String>,
    req: Request,
    next: Next,
) -> Result<Response, ApiError> {
    let given = req.headers().get(&TOKEN_HEADER).map(|v| v.as_bytes());
    if given.is_some_and(|g| constant_time_eq(g, token.as_bytes())) {
        Ok(next.run(req).await)
    } else {
        Err(ApiError(StatusCode::UNAUTHORIZED, "unauthorized".into()))
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

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct FeedRequest {
    events: Vec<Event>,
    #[serde(default)]
    seen_ids: Vec<String>,
    #[serde(default)]
    recent_datasets: Vec<String>,
    count: i64,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct FeedResponse {
    picks: Vec<Pick>,
    taste: Taste,
    seen_reset: bool,
}

async fn feed(
    State(state): State<Arc<AppState>>,
    body: Bytes,
) -> Result<Json<FeedResponse>, ApiError> {
    let req: FeedRequest = parse_body(&body)?;
    if !(1..=MAX_COUNT as i64).contains(&req.count) {
        return Err(ApiError::bad_request(format!("count は 1〜{MAX_COUNT}")));
    }
    let snap = ready(&state)?;
    let u = taste::replay(&snap.u0, &req.events, &snap.index, &state.config);
    let views = req
        .events
        .iter()
        .filter(|e| matches!(e, Event::View { .. }))
        .count();
    let mut rng = state.rng();
    let result = pick::pick_next(
        &snap.index,
        &state.config,
        &u,
        views,
        &req.seen_ids,
        &req.recent_datasets,
        req.count as usize,
        &mut rng,
    )
    .map_err(|e| ApiError::unavailable(e.to_string()))?;
    let taste = panel::taste(&snap.index, &state.config, &u)
        .map_err(|e| ApiError::unavailable(e.to_string()))?;
    Ok(Json(FeedResponse {
        picks: result.picks,
        taste,
        seen_reset: result.seen_reset,
    }))
}

#[derive(Deserialize)]
struct TasteRequest {
    events: Vec<Event>,
}

async fn taste_handler(
    State(state): State<Arc<AppState>>,
    body: Bytes,
) -> Result<Json<serde_json::Value>, ApiError> {
    let req: TasteRequest = parse_body(&body)?;
    let snap = ready(&state)?;
    let u = taste::replay(&snap.u0, &req.events, &snap.index, &state.config);
    let taste = panel::taste(&snap.index, &state.config, &u)
        .map_err(|e| ApiError::unavailable(e.to_string()))?;
    Ok(Json(serde_json::json!({ "taste": taste })))
}

async fn reload(State(state): State<Arc<AppState>>) -> Result<Json<serde_json::Value>, ApiError> {
    match state.reload().await {
        Ok(n) => {
            tracing::info!(videos = n, "索引を読み直した");
            Ok(Json(serde_json::json!({"status": "ok", "videos": n})))
        }
        Err(e) => {
            tracing::error!(error = %e, "索引の読み直しに失敗(古い索引のまま)");
            Err(ApiError(
                StatusCode::BAD_GATEWAY,
                format!("索引の読み込みに失敗: {e}"),
            ))
        }
    }
}

/// `internal_token` は INTERNAL_TOKEN の値。空でないこと(呼び出し側で確かめる)。
pub fn app(internal_token: String, state: Arc<AppState>) -> Router {
    let internal = Router::new()
        .route("/internal/ping", get(ping))
        .route("/internal/feed", post(feed))
        .route("/internal/taste", post(taste_handler))
        .route("/internal/reload", post(reload))
        .layer(middleware::from_fn_with_state(
            internal_token,
            require_token,
        ));
    Router::new()
        .route("/healthz", get(healthz))
        .merge(internal)
        .with_state(state)
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::Body, http::Request};
    use http_body_util::BodyExt;
    use loader::BoxFuture;
    use recsys_core::index::{Cluster, Index, Video};
    use serde_json::{Value, json};
    use std::sync::Mutex;
    use tower::ServiceExt;

    /// 呼ぶたびに、積んである結果を先頭から返す(最後の 1 つは返し続ける)。
    struct StubLoader(Mutex<Vec<Result<Snapshot, String>>>);

    impl Loader for StubLoader {
        fn load(&self) -> BoxFuture<'_, Result<Snapshot, LoadError>> {
            let mut q = self.0.lock().unwrap();
            let r = if q.len() > 1 {
                q.remove(0)
            } else {
                q[0].clone()
            };
            Box::pin(async move { r.map_err(LoadError) })
        }
    }

    fn snapshot(n: usize) -> Snapshot {
        let videos = (0..n)
            .map(|i| {
                let a = i as f32 * 0.7;
                Video {
                    id: format!("v{i}"),
                    dataset_id: format!("d{}", i % 2),
                    vector: vec![a.cos(), a.sin()],
                    x: i as f32 / 10.0,
                    y: 0.5,
                }
            })
            .collect();
        let clusters = (0..3)
            .map(|i| {
                let a = i as f32 * 2.0;
                Cluster {
                    id: i,
                    centroid: vec![a.cos(), a.sin()],
                    cx: 0.5,
                    cy: 0.5,
                }
            })
            .collect();
        Snapshot {
            index: Index::new(videos, clusters),
            u0: vec![1.0, 0.0],
        }
    }

    fn state_with(results: Vec<Result<Snapshot, String>>) -> Arc<AppState> {
        AppState::new(Arc::new(StubLoader(Mutex::new(results))), Config::default())
    }

    async fn loaded_app(n: usize) -> Router {
        let state = state_with(vec![Ok(snapshot(n))]);
        state.reload().await.unwrap();
        app("secret".into(), state)
    }

    async fn send(
        app: &Router,
        method: &str,
        path: &str,
        token: Option<&str>,
        body: &str,
    ) -> (StatusCode, Value) {
        let mut b = Request::builder().method(method).uri(path);
        if let Some(t) = token {
            b = b.header("X-Internal-Token", t);
        }
        let res = app
            .clone()
            .oneshot(b.body(Body::from(body.to_owned())).unwrap())
            .await
            .unwrap();
        let status = res.status();
        let bytes = res.into_body().collect().await.unwrap().to_bytes();
        (
            status,
            serde_json::from_slice(&bytes).unwrap_or(Value::Null),
        )
    }

    async fn post_json(app: &Router, path: &str, body: Value) -> (StatusCode, Value) {
        send(app, "POST", path, Some("secret"), &body.to_string()).await
    }

    #[tokio::test]
    async fn healthz_needs_no_token_and_reports_count() {
        let app = loaded_app(5).await;
        let (st, body) = send(&app, "GET", "/healthz", None, "").await;
        assert_eq!(st, StatusCode::OK);
        assert_eq!(body, json!({"status": "ok", "videos": 5}));
    }

    #[tokio::test]
    async fn healthz_is_503_before_load() {
        let app = app("secret".into(), state_with(vec![Ok(snapshot(1))]));
        let (st, body) = send(&app, "GET", "/healthz", None, "").await;
        assert_eq!(st, StatusCode::SERVICE_UNAVAILABLE);
        assert!(body["error"].is_string());
        let (st, _) = post_json(&app, "/internal/taste", json!({"events": []})).await;
        assert_eq!(st, StatusCode::SERVICE_UNAVAILABLE);
    }

    #[tokio::test]
    async fn internal_requires_token() {
        let app = loaded_app(3).await;
        for path in ["/internal/ping"] {
            assert_eq!(
                send(&app, "GET", path, None, "").await.0,
                StatusCode::UNAUTHORIZED
            );
            assert_eq!(
                send(&app, "GET", path, Some("wrong"), "").await.0,
                StatusCode::UNAUTHORIZED
            );
            assert_eq!(
                send(&app, "GET", path, Some("secre"), "").await.0,
                StatusCode::UNAUTHORIZED
            );
            assert_eq!(
                send(&app, "GET", path, Some("secret"), "").await.0,
                StatusCode::OK
            );
        }
        for path in ["/internal/feed", "/internal/taste", "/internal/reload"] {
            let (st, body) = send(&app, "POST", path, None, "{}").await;
            assert_eq!(st, StatusCode::UNAUTHORIZED, "{path}");
            assert!(body["error"].is_string());
            assert_eq!(
                send(&app, "POST", path, Some("wrong"), "{}").await.0,
                StatusCode::UNAUTHORIZED
            );
        }
    }

    #[tokio::test]
    async fn feed_validates_input() {
        let app = loaded_app(6).await;
        for count in [0, 4, -1] {
            let (st, body) = post_json(
                &app,
                "/internal/feed",
                json!({"events": [], "count": count}),
            )
            .await;
            assert_eq!(st, StatusCode::BAD_REQUEST, "count={count}");
            assert!(body["error"].is_string());
        }
        let bad_type = json!({"events": [{"type": "share", "videoId": "v0"}], "count": 1});
        assert_eq!(
            post_json(&app, "/internal/feed", bad_type.clone()).await.0,
            StatusCode::BAD_REQUEST
        );
        assert_eq!(
            post_json(
                &app,
                "/internal/taste",
                json!({"events": bad_type["events"]})
            )
            .await
            .0,
            StatusCode::BAD_REQUEST
        );
        let (st, _) = send(&app, "POST", "/internal/feed", Some("secret"), "not json").await;
        assert_eq!(st, StatusCode::BAD_REQUEST);
        let (st, _) = post_json(&app, "/internal/feed", json!({"events": []})).await;
        assert_eq!(st, StatusCode::BAD_REQUEST, "count がない");
    }

    fn assert_taste(t: &Value) {
        assert!(t["x"].is_number() && t["y"].is_number());
        let shares = t["shares"].as_array().unwrap();
        assert_eq!(shares.len(), 3);
        let total: u64 = shares.iter().map(|s| s["pct"].as_u64().unwrap()).sum();
        assert_eq!(total, 100);
        assert!(shares.iter().all(|s| s["clusterId"].is_i64()));
    }

    #[tokio::test]
    async fn feed_returns_picks_taste_and_seen_reset() {
        let app = loaded_app(6).await;
        let events = json!([
            {"type": "view", "videoId": "v0", "ratio": 0.9},
            {"type": "like", "videoId": "v0", "liked": true}
        ]);
        let (st, body) = post_json(
            &app,
            "/internal/feed",
            json!({"events": events, "seenIds": ["v0"], "recentDatasets": ["d0"], "count": 3}),
        )
        .await;
        assert_eq!(st, StatusCode::OK, "{body}");
        let picks = body["picks"].as_array().unwrap();
        assert_eq!(picks.len(), 3);
        let mut ids: Vec<&str> = picks
            .iter()
            .map(|p| p["videoId"].as_str().unwrap())
            .collect();
        assert!(!ids.contains(&"v0"));
        ids.sort();
        ids.dedup();
        assert_eq!(ids.len(), 3);
        assert!(picks.iter().all(|p| p["reason"].is_string()));
        assert_eq!(body["seenReset"], json!(false));
        assert_taste(&body["taste"]);

        // 全部見た → seenReset
        let all: Vec<String> = (0..6).map(|i| format!("v{i}")).collect();
        let (st, body) = post_json(
            &app,
            "/internal/feed",
            json!({"events": [], "seenIds": all, "count": 1}),
        )
        .await;
        assert_eq!(st, StatusCode::OK);
        assert_eq!(body["seenReset"], json!(true));
        assert_eq!(body["picks"].as_array().unwrap().len(), 1);
    }

    #[tokio::test]
    async fn taste_returns_shares_summing_to_100() {
        let app = loaded_app(6).await;
        let (st, body) = post_json(
            &app,
            "/internal/taste",
            json!({"events": [{"type": "view", "videoId": "v2", "ratio": 1.0}]}),
        )
        .await;
        assert_eq!(st, StatusCode::OK);
        assert_taste(&body["taste"]);
        assert!(body.get("picks").is_none());
    }

    #[tokio::test]
    async fn empty_index_is_503() {
        let app = loaded_app(0).await;
        let (st, _) = post_json(&app, "/internal/feed", json!({"events": [], "count": 1})).await;
        assert_eq!(st, StatusCode::SERVICE_UNAVAILABLE);
    }

    #[tokio::test]
    async fn reload_swaps_index_and_failure_keeps_old() {
        let state = state_with(vec![
            Ok(snapshot(3)),
            Ok(snapshot(8)),
            Err("db down".into()),
        ]);
        state.reload().await.unwrap();
        let app = app("secret".into(), state);
        assert_eq!(send(&app, "GET", "/healthz", None, "").await.1["videos"], 3);

        let (st, body) = send(&app, "POST", "/internal/reload", Some("secret"), "").await;
        assert_eq!((st, body["videos"].as_u64()), (StatusCode::OK, Some(8)));
        assert_eq!(send(&app, "GET", "/healthz", None, "").await.1["videos"], 8);
        let (st, _) = post_json(&app, "/internal/feed", json!({"events": [], "count": 1})).await;
        assert_eq!(st, StatusCode::OK);

        let (st, body) = send(&app, "POST", "/internal/reload", Some("secret"), "").await;
        assert_eq!(st, StatusCode::BAD_GATEWAY);
        assert!(body["error"].is_string());
        assert_eq!(send(&app, "GET", "/healthz", None, "").await.1["videos"], 8);
    }

    #[tokio::test(start_paused = true)]
    async fn initial_load_retries_until_success() {
        let state = state_with(vec![
            Err("down".into()),
            Err("down".into()),
            Ok(snapshot(2)),
        ]);
        let app = app("secret".into(), state.clone());
        assert_eq!(
            send(&app, "GET", "/healthz", None, "").await.0,
            StatusCode::SERVICE_UNAVAILABLE
        );
        state.load_with_retry().await;
        assert_eq!(
            send(&app, "GET", "/healthz", None, "").await.0,
            StatusCode::OK
        );
    }
}
