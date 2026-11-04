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
    pub fn new(videos: Vec<Video>, clusters: Vec<Cluster>) -> Self {
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
