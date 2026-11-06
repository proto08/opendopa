//! DB を使う統合テスト。`mise run recsys-db-test` が使い捨ての DB を作り、
//! 環境変数 RECSYS_TEST_DATABASE_URL(読み取り専用ロールの接続文字列)を渡して実行する。
//! 環境変数がなければ何もしない(`cargo test` 単体では DB なしで通る)。

use recsys_server::loader::{Loader, PgLoader};
use sqlx::postgres::PgPoolOptions;

fn url() -> Option<String> {
    std::env::var("RECSYS_TEST_DATABASE_URL").ok()
}

/// 用意された DB(動画 2 本のうち status='ok' は 1 本、クラスタ 1 つ)を読める。
#[tokio::test]
async fn loads_only_ok_videos_from_db() {
    let Some(url) = url() else { return };
    let snap = PgLoader::new(&url).unwrap().load().await.unwrap();
    assert_eq!(snap.index.len(), 1);
    assert!(snap.index.video("v1").is_some());
    assert!(snap.index.video("v2").is_none(), "excluded は読まない");
    assert_eq!(snap.index.clusters().len(), 1);
    assert_eq!(snap.u0.len(), 1024);
    assert_eq!(snap.index.videos()[0].dataset_id, "d");
}

/// 読み取り専用ロールでは、書き込みも、読んではいけない列の参照もできない。
#[tokio::test]
async fn recsys_role_cannot_write() {
    let Some(url) = url() else { return };
    let pool = PgPoolOptions::new()
        .max_connections(1)
        .connect(&url)
        .await
        .unwrap();
    for sql in [
        "INSERT INTO meta (key, value) VALUES ('x', '1')",
        "UPDATE clusters SET name = 'x'",
        "DELETE FROM embeddings",
        "SELECT scene FROM videos",
    ] {
        assert!(sqlx::query(sql).execute(&pool).await.is_err(), "{sql}");
    }
}
