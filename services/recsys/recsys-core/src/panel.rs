//! 好みパネルの値(設計書 §7.5)。地図上の現在地と、クラスタごとの割合。

use serde::Serialize;

use crate::{
    config::Config,
    index::{EmptyIndex, Index},
    taste::dot,
};

/// 温度つき softmax。数値が溢れないよう、最大値を引いてから指数を取る。
pub(crate) fn softmax(values: &[f64], temperature: f64) -> Vec<f64> {
    let max = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let exps: Vec<f64> = values
        .iter()
        .map(|v| ((v - max) / temperature).exp())
        .collect();
    let sum: f64 = exps.iter().sum();
    exps.into_iter().map(|e| e / sum).collect()
}

/// 地図上の「いまの好み」。`sim_i = u・v_i`、`w_i = softmax(sim_i / TAU_MAP)`、`(x, y) = Σ w_i (x_i, y_i)`。
/// 動画の座標が 0〜1 なら、結果も 0〜1 に入る(重み付き平均なので)。
pub fn taste_position(index: &Index, config: &Config, u: &[f32]) -> Result<(f32, f32), EmptyIndex> {
    if index.is_empty() {
        return Err(EmptyIndex);
    }
    let sims: Vec<f64> = index
        .videos()
        .iter()
        .map(|v| dot(u, &v.vector) as f64)
        .collect();
    let w = softmax(&sims, config.tau_map as f64);
    let (mut x, mut y) = (0.0f64, 0.0f64);
    for (w, v) in w.iter().zip(index.videos()) {
        x += w * v.x as f64;
        y += w * v.y as f64;
    }
    Ok((x as f32, y as f32))
}

/// クラスタ 1 つの割合(百分率の整数)。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Share {
    pub cluster_id: i32,
    pub pct: u32,
}

/// `share_k = softmax(u・centroid_k / TAU)` を、合計が 100 の整数に丸める(最大剰余法)。
/// クラスタがなければ空。順序は索引のクラスタの順。
pub fn shares(index: &Index, config: &Config, u: &[f32]) -> Vec<Share> {
    let clusters = index.clusters();
    if clusters.is_empty() {
        return Vec::new();
    }
    let sims: Vec<f64> = clusters
        .iter()
        .map(|c| dot(u, &c.centroid) as f64)
        .collect();
    let p = softmax(&sims, config.tau as f64);
    let pcts = largest_remainder(&p, 100);
    clusters
        .iter()
        .zip(pcts)
        .map(|(c, pct)| Share {
            cluster_id: c.id,
            pct,
        })
        .collect()
}

/// 確率 `p`(合計 1)を、合計が `total` の整数に最大剰余法で丸める。
/// 端数が同じときは、前のクラスタを先にする。
fn largest_remainder(p: &[f64], total: u32) -> Vec<u32> {
    let scaled: Vec<f64> = p.iter().map(|p| p * total as f64).collect();
    let mut out: Vec<u32> = scaled.iter().map(|s| s.floor() as u32).collect();
    let mut rest = total.saturating_sub(out.iter().sum());
    let mut order: Vec<usize> = (0..p.len()).collect();
    order.sort_by(|&a, &b| {
        let (fa, fb) = (scaled[a].fract(), scaled[b].fract());
        fb.partial_cmp(&fa).unwrap_or(std::cmp::Ordering::Equal)
    });
    for i in order {
        if rest == 0 {
            break;
        }
        out[i] += 1;
        rest -= 1;
    }
    out
}

/// 右パネルの値。
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Taste {
    pub x: f32,
    pub y: f32,
    pub shares: Vec<Share>,
}

pub fn taste(index: &Index, config: &Config, u: &[f32]) -> Result<Taste, EmptyIndex> {
    let (x, y) = taste_position(index, config, u)?;
    Ok(Taste {
        x,
        y,
        shares: shares(index, config, u),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        index::{Cluster, Video},
        rng::Rng,
        taste::normalize,
    };

    fn rand_vec(rng: &mut Rng, dim: usize) -> Vec<f32> {
        let v: Vec<f32> = (0..dim).map(|_| rng.next_f64() as f32 - 0.5).collect();
        normalize(&v).unwrap()
    }

    fn index(rng: &mut Rng, n: usize, k: usize) -> Index {
        let videos = (0..n)
            .map(|i| Video {
                id: format!("v{i}"),
                dataset_id: "d".into(),
                vector: rand_vec(rng, 8),
                x: rng.next_f64() as f32,
                y: rng.next_f64() as f32,
            })
            .collect();
        let clusters = (0..k)
            .map(|i| Cluster {
                id: i as i32,
                centroid: rand_vec(rng, 8),
                cx: 0.5,
                cy: 0.5,
            })
            .collect();
        Index::new(videos, clusters)
    }

    #[test]
    fn shares_sum_to_100_for_random_u() {
        let mut rng = Rng::new(42);
        let idx = index(&mut rng, 30, 7);
        let cfg = Config::default();
        for _ in 0..100 {
            let u = rand_vec(&mut rng, 8);
            let s = shares(&idx, &cfg, &u);
            assert_eq!(s.len(), 7);
            assert_eq!(s.iter().map(|s| s.pct).sum::<u32>(), 100);
        }
    }

    #[test]
    fn shares_with_flat_distribution_are_distributed_evenly() {
        // 3 クラスタが全く同じ類似度 → 33,33,33 に余り 1 を先頭へ。
        let c = |id| Cluster {
            id,
            centroid: vec![1.0, 0.0],
            cx: 0.0,
            cy: 0.0,
        };
        let idx = Index::new(vec![], vec![c(1), c(2), c(3)]);
        let s = shares(&idx, &Config::default(), &[1.0, 0.0]);
        let pcts: Vec<u32> = s.iter().map(|s| s.pct).collect();
        assert_eq!(pcts, [34, 33, 33]);
    }

    #[test]
    fn no_clusters_gives_empty_shares() {
        let idx = Index::new(vec![], vec![]);
        assert!(shares(&idx, &Config::default(), &[1.0]).is_empty());
    }

    #[test]
    fn position_stays_in_unit_square_and_is_deterministic() {
        let mut rng = Rng::new(3);
        let idx = index(&mut rng, 50, 3);
        let cfg = Config::default();
        for _ in 0..50 {
            let u = rand_vec(&mut rng, 8);
            let (x, y) = taste_position(&idx, &cfg, &u).unwrap();
            assert!((0.0..=1.0).contains(&x) && (0.0..=1.0).contains(&y));
            assert_eq!(taste_position(&idx, &cfg, &u).unwrap(), (x, y));
        }
    }

    #[test]
    fn position_follows_the_closest_video() {
        let v = |id: &str, vec: Vec<f32>, x, y| Video {
            id: id.into(),
            dataset_id: "d".into(),
            vector: vec,
            x,
            y,
        };
        let idx = Index::new(
            vec![
                v("a", vec![1.0, 0.0], 0.1, 0.2),
                v("b", vec![0.0, 1.0], 0.9, 0.8),
            ],
            vec![],
        );
        let (x, y) = taste_position(&idx, &Config::default(), &[1.0, 0.0]).unwrap();
        assert!((x - 0.1).abs() < 0.01 && (y - 0.2).abs() < 0.01);
    }

    #[test]
    fn empty_index_is_an_error() {
        let idx = Index::new(vec![], vec![]);
        assert_eq!(
            taste_position(&idx, &Config::default(), &[1.0]),
            Err(EmptyIndex)
        );
        assert!(taste(&idx, &Config::default(), &[1.0]).is_err());
    }
}
