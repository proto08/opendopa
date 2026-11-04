//! 動画とクラスタの索引(インメモリ)。DB からの読み込みは recsys-server 側(#41)。

use std::collections::HashMap;

/// 索引に載せる動画 1 本。
#[derive(Debug, Clone, PartialEq)]
pub struct Video {
    pub id: String,
    pub dataset_id: String,
    /// 長さ 1 の埋め込み。
    pub vector: Vec<f32>,
    /// 地図の座標。
    pub x: f32,
    pub y: f32,
}

/// クラスタ 1 つ。
#[derive(Debug, Clone, PartialEq)]
pub struct Cluster {
    pub id: i32,
    /// 長さ 1 の重心。
    pub centroid: Vec<f32>,
    pub cx: f32,
    pub cy: f32,
}

/// 動画 ID から引ける索引。`videos()` は渡された順を保つ。
#[derive(Debug, Clone, Default)]
pub struct Index {
    videos: Vec<Video>,
    by_id: HashMap<String, usize>,
    clusters: Vec<Cluster>,
}

impl Index {
    /// 同じ ID の動画があれば、後ろのものを無視する。
    /// 全動画とクラスタの重心は、同じ次元でなければならない(開発中は `debug_assert` で確かめる)。
    pub fn new(videos: Vec<Video>, clusters: Vec<Cluster>) -> Self {
        let dim = videos
            .first()
            .map(|v| v.vector.len())
            .or_else(|| clusters.first().map(|c| c.centroid.len()));
        debug_assert!(
            videos.iter().all(|v| Some(v.vector.len()) == dim)
                && clusters.iter().all(|c| Some(c.centroid.len()) == dim),
            "埋め込みの次元がそろっていない"
        );
        let mut by_id = HashMap::with_capacity(videos.len());
        let mut kept = Vec::with_capacity(videos.len());
        for v in videos {
            if !by_id.contains_key(&v.id) {
                by_id.insert(v.id.clone(), kept.len());
                kept.push(v);
            }
        }
        Self {
            videos: kept,
            by_id,
            clusters,
        }
    }

    pub fn video(&self, id: &str) -> Option<&Video> {
        self.by_id.get(id).map(|&i| &self.videos[i])
    }

    pub fn videos(&self) -> &[Video] {
        &self.videos
    }

    pub fn clusters(&self) -> &[Cluster] {
        &self.clusters
    }

    pub fn len(&self) -> usize {
        self.videos.len()
    }

    pub fn is_empty(&self) -> bool {
        self.videos.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn video(id: &str, x: f32) -> Video {
        Video {
            id: id.into(),
            dataset_id: "d".into(),
            vector: vec![1.0, 0.0],
            x,
            y: 0.0,
        }
    }

    #[test]
    fn duplicate_id_keeps_first() {
        let idx = Index::new(
            vec![video("a", 1.0), video("b", 2.0), video("a", 3.0)],
            vec![],
        );
        assert_eq!(idx.len(), 2);
        assert_eq!(idx.video("a").unwrap().x, 1.0);
    }

    #[test]
    fn videos_keep_given_order() {
        let idx = Index::new(
            vec![video("c", 0.0), video("a", 0.0), video("b", 0.0)],
            vec![],
        );
        let ids: Vec<&str> = idx.videos().iter().map(|v| v.id.as_str()).collect();
        assert_eq!(ids, ["c", "a", "b"]);
        assert!(idx.video("zzz").is_none());
    }
}
