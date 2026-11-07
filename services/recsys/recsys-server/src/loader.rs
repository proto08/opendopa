//! 動画の索引の読み込み(設計書 §6.6)。DB からは読み取りのみ。
//!
//! 読み込み先は `Loader` trait にして、テストでは差し替えられるようにする。

use std::{future::Future, pin::Pin};

use recsys_core::{
    index::{Cluster, Index, Video},
    taste::normalize,
};
use sqlx::{PgPool, Row, postgres::PgPoolOptions};

/// 読み込んだ索引と、好みの初期値 `u0`(全動画の重心。設計書 §7.2)。
#[derive(Debug, Clone)]
pub struct Snapshot {
    pub index: Index,
    pub u0: Vec<f32>,
}

#[derive(Debug)]
pub struct LoadError(pub String);

impl std::fmt::Display for LoadError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for LoadError {}

pub type BoxFuture<'a, T> = Pin<Box<dyn Future<Output = T> + Send + 'a>>;

/// 索引の読み込み元。
pub trait Loader: Send + Sync {
    fn load(&self) -> BoxFuture<'_, Result<Snapshot, LoadError>>;
}

/// pgvector の文字列表現 `[0.1,0.2,...]` を読む。
pub fn parse_vector(s: &str) -> Result<Vec<f32>, LoadError> {
    let inner = s
        .trim()
        .strip_prefix('[')
        .and_then(|s| s.strip_suffix(']'))
        .ok_or_else(|| {
            LoadError(format!(
                "ベクトルの形が不正: {}",
                s.chars().take(20).collect::<String>()
            ))
        })?;
    inner
        .split(',')
        .map(|x| {
            x.trim()
                .parse::<f32>()
                .map_err(|e| LoadError(format!("ベクトルの要素が数でない: {e}")))
        })
        .collect()
}

/// 動画・クラスタ・`u0` の材料から、次元をそろえて `Snapshot` を作る。
/// `centroid` がない(`meta` に未登録)ときは、動画の埋め込みの平均を長さ 1 にして使う。
pub fn build_snapshot(
    videos: Vec<Video>,
    clusters: Vec<Cluster>,
    centroid: Option<Vec<f32>>,
) -> Result<Snapshot, LoadError> {
    let dim = videos
        .first()
        .map(|v| v.vector.len())
        .or_else(|| clusters.first().map(|c| c.centroid.len()))
        .or_else(|| centroid.as_ref().map(Vec::len))
        .unwrap_or(0);
    if videos.iter().any(|v| v.vector.len() != dim)
        || clusters.iter().any(|c| c.centroid.len() != dim)
        || centroid.as_ref().is_some_and(|c| c.len() != dim)
    {
        return Err(LoadError("埋め込みの次元がそろっていない".into()));
    }
    let u0 = match centroid.as_deref().and_then(normalize) {
        Some(u0) => u0,
        None => {
            let mut sum = vec![0.0f32; dim];
            for v in &videos {
                for (s, x) in sum.iter_mut().zip(&v.vector) {
                    *s += x;
                }
            }
            normalize(&sum).unwrap_or(sum)
        }
    };
    Ok(Snapshot {
        index: Index::new(videos, clusters),
        u0,
    })
}

/// PostgreSQL(読み取り専用ロール)から読む。
pub struct PgLoader {
    pool: PgPool,
}

impl PgLoader {
    /// 接続は最初の読み込みまで張らない。
    pub fn new(database_url: &str) -> Result<Self, LoadError> {
        let pool = PgPoolOptions::new()
            .max_connections(2)
            .acquire_timeout(std::time::Duration::from_secs(10))
            .connect_lazy(database_url)
            .map_err(|e| LoadError(format!("RECSYS_DATABASE_URL が不正: {e}")))?;
        Ok(Self { pool })
    }

    async fn load_inner(&self) -> Result<Snapshot, sqlx::Error> {
        // 3 つの読み込みの間で内容がずれないよう、読み取り専用のスナップショットで読む
        let mut tx = self.pool.begin().await?;
        sqlx::query("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            .execute(&mut *tx)
            .await?;

        let rows = sqlx::query(
            "SELECT e.video_id, v.dataset_id, e.embedding::text AS embedding, e.x, e.y \
             FROM embeddings e JOIN videos v ON v.id = e.video_id \
             WHERE v.status = 'ok' ORDER BY e.video_id",
        )
        .fetch_all(&mut *tx)
        .await?;
        let mut videos = Vec::with_capacity(rows.len());
        for r in rows {
            videos.push(Video {
                id: r.try_get("video_id")?,
                dataset_id: r.try_get("dataset_id")?,
                vector: decode_vector(&r.try_get::<String, _>("embedding")?)?,
                x: r.try_get("x")?,
                y: r.try_get("y")?,
            });
        }

        let rows =
            sqlx::query("SELECT id, centroid::text AS centroid, cx, cy FROM clusters ORDER BY id")
                .fetch_all(&mut *tx)
                .await?;
        let mut clusters = Vec::with_capacity(rows.len());
        for r in rows {
            clusters.push(Cluster {
                id: r.try_get("id")?,
                centroid: decode_vector(&r.try_get::<String, _>("centroid")?)?,
                cx: r.try_get("cx")?,
                cy: r.try_get("cy")?,
            });
        }

        let centroid: Option<String> =
            sqlx::query_scalar("SELECT value::text FROM meta WHERE key = 'centroid'")
                .fetch_optional(&mut *tx)
                .await?;
        tx.rollback().await?;

        let centroid = centroid
            .map(|s| {
                serde_json::from_str::<Vec<f32>>(&s).map_err(|e| {
                    sqlx::Error::Decode(format!("meta.centroid が数の配列でない: {e}").into())
                })
            })
            .transpose()?;
        build_snapshot(videos, clusters, centroid).map_err(|e| sqlx::Error::Decode(e.0.into()))
    }
}

fn decode_vector(s: &str) -> Result<Vec<f32>, sqlx::Error> {
    parse_vector(s).map_err(|e| sqlx::Error::Decode(e.0.into()))
}

impl Loader for PgLoader {
    fn load(&self) -> BoxFuture<'_, Result<Snapshot, LoadError>> {
        Box::pin(async move {
            self.load_inner()
                .await
                .map_err(|e| LoadError(e.to_string()))
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn video(id: &str, v: Vec<f32>) -> Video {
        Video {
            id: id.into(),
            dataset_id: "d".into(),
            vector: v,
            x: 0.0,
            y: 0.0,
        }
    }

    #[test]
    fn parses_pgvector_text() {
        assert_eq!(parse_vector("[1,0.5,-2e-1]").unwrap(), [1.0, 0.5, -0.2]);
        assert!(parse_vector("1,2").is_err());
        assert!(parse_vector("[a]").is_err());
    }

    #[test]
    fn u0_falls_back_to_mean_of_embeddings() {
        let s = build_snapshot(
            vec![video("a", vec![1.0, 0.0]), video("b", vec![0.0, 1.0])],
            vec![],
            None,
        )
        .unwrap();
        let r = 0.5f32.sqrt();
        assert!((s.u0[0] - r).abs() < 1e-6 && (s.u0[1] - r).abs() < 1e-6);
    }

    #[test]
    fn u0_uses_meta_centroid_normalized() {
        let s = build_snapshot(
            vec![video("a", vec![1.0, 0.0])],
            vec![],
            Some(vec![0.0, 3.0]),
        )
        .unwrap();
        assert_eq!(s.u0, [0.0, 1.0]);
    }

    #[test]
    fn mismatched_dimensions_are_an_error() {
        assert!(
            build_snapshot(
                vec![video("a", vec![1.0, 0.0]), video("b", vec![1.0])],
                vec![],
                None
            )
            .is_err()
        );
        assert!(build_snapshot(vec![video("a", vec![1.0, 0.0])], vec![], Some(vec![1.0])).is_err());
    }
}
