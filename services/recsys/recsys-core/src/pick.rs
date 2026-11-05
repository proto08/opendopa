//! 次の動画の選び方(設計書 §7.4)。

use std::collections::HashSet;

use serde::Serialize;

use crate::{
    config::Config,
    index::{EmptyIndex, Index},
    panel::softmax,
    rng::Rng,
    taste::dot,
};

/// 選んだ理由。JSON では `first` / `explore_cold` / `near` / `adventure`。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Reason {
    First,
    ExploreCold,
    Near,
    Adventure,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Pick {
    pub video_id: String,
    pub reason: Reason,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PickResult {
    pub picks: Vec<Pick>,
    /// 未視聴が尽きたので、`seen_ids` を空として扱って選んだ。受け取った側が impressions を消す。
    pub seen_reset: bool,
}

/// 1 回の呼び出しで選べる本数の上限。
pub const MAX_COUNT: usize = 3;

/// 次の動画を `count`(1〜3 に丸める)本、重複なく選ぶ。
///
/// - `event_count`: `events` のうち `view` の数。
/// - `seen_ids`: 配信済みの動画 ID。未視聴が空なら、空として扱って全体から選び、`seen_reset=true`。
/// - `recent_datasets`: 配信済みのデータセット。新しい順。
/// - 選んだ動画は、次の選択の未視聴から外れ、連続数にも数える。
/// - 候補が尽きたら、`count` より少なく返す(1 本は必ず返す)。
#[allow(clippy::too_many_arguments)] // 設計書の引数に、索引と設定を足したもの
pub fn pick_next(
    index: &Index,
    config: &Config,
    u: &[f32],
    event_count: usize,
    seen_ids: &[String],
    recent_datasets: &[String],
    count: usize,
    rng: &mut Rng,
) -> Result<PickResult, EmptyIndex> {
    if index.is_empty() {
        return Err(EmptyIndex);
    }
    let videos = index.videos();
    let count = count.clamp(1, MAX_COUNT);

    let is_first = seen_ids.is_empty();
    let mut seen: HashSet<&str> = seen_ids.iter().map(String::as_str).collect();
    let seen_reset = videos.iter().all(|v| seen.contains(v.id.as_str()));
    if seen_reset {
        seen.clear();
    }

    // 新しい順。この呼び出しで選んだものを先頭に足していく。
    let mut recent: Vec<&str> = recent_datasets.iter().map(String::as_str).collect();
    // 「出ているデータセット」は、配信済みの動画と recent_datasets の和集合。
    let mut shown: HashSet<&str> = recent.iter().copied().collect();
    if !seen_reset {
        shown.extend(
            videos
                .iter()
                .filter(|v| seen.contains(v.id.as_str()))
                .map(|v| v.dataset_id.as_str()),
        );
    }

    let mut picks = Vec::with_capacity(count);
    for n in 0..count {
        let mut pool: Vec<usize> = (0..videos.len())
            .filter(|&i| !seen.contains(videos[i].id.as_str()))
            .collect();
        if pool.is_empty() {
            break;
        }
        // 連続制限: 直近 max_streak 本が同じデータセットなら、それ以外から選ぶ。
        if let Some(streak) = streak_dataset(&recent, config.max_streak) {
            let others: Vec<usize> = pool
                .iter()
                .copied()
                .filter(|&i| videos[i].dataset_id != streak)
                .collect();
            if !others.is_empty() {
                pool = others;
            }
        }

        let cold = event_count < config.cold_start_n;
        let (i, reason) = if is_first && n == 0 {
            let i = if cold {
                pick_by_new_dataset(index, &pool, &shown, rng)
            } else {
                pick_near(index, config, u, &pool, rng)
            };
            (i, Reason::First)
        } else if cold {
            (
                pick_by_new_dataset(index, &pool, &shown, rng),
                Reason::ExploreCold,
            )
        } else if rng.next_f64() < config.explore as f64 {
            (
                pick_adventure(index, u, &pool, recent.first().copied(), rng),
                Reason::Adventure,
            )
        } else {
            (pick_near(index, config, u, &pool, rng), Reason::Near)
        };

        let v = &videos[i];
        seen.insert(v.id.as_str());
        shown.insert(v.dataset_id.as_str());
        recent.insert(0, v.dataset_id.as_str());
        picks.push(Pick {
            video_id: v.id.clone(),
            reason,
        });
    }
    Ok(PickResult { picks, seen_reset })
}

/// 新しい順の `recent` の先頭 `max_streak` 本が全部同じデータセットなら、それを返す。
fn streak_dataset<'a>(recent: &[&'a str], max_streak: usize) -> Option<&'a str> {
    let head = recent.get(..max_streak)?;
    let first = *head.first()?;
    head.iter().all(|d| *d == first).then_some(first)
}

/// まだ出ていないデータセットを一様に選び、その中から一様に選ぶ。
/// 候補のデータセットが全部出ていれば、候補全体のデータセットから選ぶ。
fn pick_by_new_dataset(
    index: &Index,
    pool: &[usize],
    shown: &HashSet<&str>,
    rng: &mut Rng,
) -> usize {
    let videos = index.videos();
    let mut datasets: Vec<&str> = Vec::new(); // 初めて現れた順(再現性のため)
    for &i in pool {
        let d = videos[i].dataset_id.as_str();
        if !datasets.contains(&d) {
            datasets.push(d);
        }
    }
    let fresh: Vec<&str> = datasets
        .iter()
        .copied()
        .filter(|d| !shown.contains(d))
        .collect();
    let chosen_from = if fresh.is_empty() { &datasets } else { &fresh };
    let dataset = chosen_from[rng.below(chosen_from.len())];
    let in_dataset: Vec<usize> = pool
        .iter()
        .copied()
        .filter(|&i| videos[i].dataset_id == dataset)
        .collect();
    in_dataset[rng.below(in_dataset.len())]
}

/// 類似度の降順(同点は索引の順)に並べた `pool`。
fn sorted_by_sim(index: &Index, u: &[f32], pool: &[usize]) -> Vec<(usize, f32)> {
    let videos = index.videos();
    let mut v: Vec<(usize, f32)> = pool
        .iter()
        .map(|&i| (i, dot(u, &videos[i].vector)))
        .collect();
    v.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(&b.0)));
    v
}

/// 類似度の上位 `topk` から、`p_i ∝ exp(sim_i / TAU)` で選ぶ。
fn pick_near(index: &Index, config: &Config, u: &[f32], pool: &[usize], rng: &mut Rng) -> usize {
    let mut sorted = sorted_by_sim(index, u, pool);
    sorted.truncate(config.topk.max(1));
    let sims: Vec<f64> = sorted.iter().map(|s| s.1 as f64).collect();
    let p = softmax(&sims, config.tau as f64);
    let r = rng.next_f64();
    let mut acc = 0.0;
    for (s, p) in sorted.iter().zip(&p) {
        acc += p;
        if r < acc {
            return s.0;
        }
    }
    sorted[sorted.len() - 1].0
}

/// 類似度が下位半分の候補から、直前と違うデータセットを優先して一様に選ぶ。
/// 下位半分は、類似度の昇順の先頭 `ceil(n/2)` 本。直前と違うものがなければ下位半分全体から選ぶ。
fn pick_adventure(
    index: &Index,
    u: &[f32],
    pool: &[usize],
    last: Option<&str>,
    rng: &mut Rng,
) -> usize {
    let videos = index.videos();
    let sorted = sorted_by_sim(index, u, pool);
    let half = sorted.len().div_ceil(2);
    let lower: Vec<usize> = sorted[sorted.len() - half..].iter().map(|s| s.0).collect();
    let different: Vec<usize> = lower
        .iter()
        .copied()
        .filter(|&i| Some(videos[i].dataset_id.as_str()) != last)
        .collect();
    let from = if different.is_empty() {
        &lower
    } else {
        &different
    };
    from[rng.below(from.len())]
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{index::Video, taste::normalize};

    fn rand_vec(rng: &mut Rng, dim: usize) -> Vec<f32> {
        let v: Vec<f32> = (0..dim).map(|_| rng.next_f64() as f32 - 0.5).collect();
        normalize(&v).unwrap()
    }

    fn index(datasets: usize, per: usize, seed: u64) -> Index {
        let mut rng = Rng::new(seed);
        let mut videos = Vec::new();
        for d in 0..datasets {
            for i in 0..per {
                videos.push(Video {
                    id: format!("d{d}-{i}"),
                    dataset_id: format!("ds{d}"),
                    vector: rand_vec(&mut rng, 16),
                    x: 0.5,
                    y: 0.5,
                });
            }
        }
        Index::new(videos, vec![])
    }

    fn u(seed: u64) -> Vec<f32> {
        rand_vec(&mut Rng::new(seed), 16)
    }

    fn run(
        idx: &Index,
        cfg: &Config,
        ec: usize,
        seen: &[String],
        recent: &[String],
        count: usize,
        seed: u64,
    ) -> PickResult {
        pick_next(
            idx,
            cfg,
            &u(99),
            ec,
            seen,
            recent,
            count,
            &mut Rng::new(seed),
        )
        .unwrap()
    }

    fn ds_of(idx: &Index, id: &str) -> String {
        idx.video(id).unwrap().dataset_id.clone()
    }

    #[test]
    fn first_pick_has_reason_first() {
        let idx = index(4, 10, 1);
        let r = run(&idx, &Config::default(), 0, &[], &[], 1, 5);
        assert_eq!(r.picks.len(), 1);
        assert_eq!(r.picks[0].reason, Reason::First);
        assert!(!r.seen_reset);
    }

    #[test]
    fn cold_start_visits_new_datasets_first() {
        let idx = index(4, 10, 1);
        let cfg = Config::default();
        let mut seen: Vec<String> = Vec::new();
        let mut recent: Vec<String> = Vec::new();
        let mut datasets = HashSet::new();
        for k in 0..3 {
            let r = run(&idx, &cfg, k, &seen, &recent, 1, 10 + k as u64);
            let id = r.picks[0].video_id.clone();
            if k > 0 {
                assert_eq!(r.picks[0].reason, Reason::ExploreCold);
            }
            let d = ds_of(&idx, &id);
            assert!(datasets.insert(d.clone()), "出ていないデータセットから選ぶ");
            seen.push(id);
            recent.insert(0, d);
        }
    }

    #[test]
    fn after_cold_start_it_is_near_or_adventure() {
        let idx = index(4, 50, 2);
        let seen = vec!["d0-0".to_string()];
        let mut cfg = Config {
            explore: 0.0,
            ..Config::default()
        };
        for seed in 0..20 {
            let r = run(&idx, &cfg, 3, &seen, &[], 1, seed);
            assert_eq!(r.picks[0].reason, Reason::Near);
        }
        cfg.explore = 1.0;
        for seed in 0..20 {
            let r = run(&idx, &cfg, 3, &seen, &[], 1, seed);
            assert_eq!(r.picks[0].reason, Reason::Adventure);
        }
    }

    #[test]
    fn near_picks_from_top_k() {
        let idx = index(2, 100, 3);
        let cfg = Config {
            explore: 0.0,
            ..Config::default()
        };
        let user = u(99);
        let top: HashSet<String> = sorted_by_sim(&idx, &user, &(0..idx.len()).collect::<Vec<_>>())
            .iter()
            .take(cfg.topk)
            .map(|s| idx.videos()[s.0].id.clone())
            .collect();
        for seed in 0..50 {
            // 連続制限が効かないよう、直近は空にする。
            let r = run(&idx, &cfg, 5, &["x".into()], &[], 1, seed);
            assert!(top.contains(&r.picks[0].video_id));
        }
    }

    #[test]
    fn adventure_picks_from_lower_half_and_avoids_last_dataset() {
        let idx = index(3, 40, 4);
        let cfg = Config {
            explore: 1.0,
            ..Config::default()
        };
        let user = u(99);
        let sorted = sorted_by_sim(&idx, &user, &(0..idx.len()).collect::<Vec<_>>());
        let lower: HashSet<String> = sorted[sorted.len() / 2..]
            .iter()
            .map(|s| idx.videos()[s.0].id.clone())
            .collect();
        for seed in 0..50 {
            let r = run(&idx, &cfg, 5, &["x".into()], &["ds1".into()], 1, seed);
            let id = &r.picks[0].video_id;
            assert!(lower.contains(id));
            assert_ne!(ds_of(&idx, id), "ds1");
        }
    }

    #[test]
    fn no_dataset_streak_of_three_in_1000_picks() {
        let idx = index(4, 500, 5);
        let cfg = Config::default();
        let mut rng = Rng::new(77);
        let mut seen: Vec<String> = Vec::new();
        let mut recent: Vec<String> = Vec::new();
        for k in 0..1000 {
            let r =
                pick_next(&idx, &cfg, &u(k as u64 % 7), k, &seen, &recent, 1, &mut rng).unwrap();
            assert!(!r.seen_reset);
            let id = r.picks[0].video_id.clone();
            recent.insert(0, ds_of(&idx, &id));
            seen.push(id);
            if recent.len() >= 3 {
                assert!(
                    !(recent[0] == recent[1] && recent[1] == recent[2]),
                    "{k} 本目で同じデータセットが 3 連続"
                );
            }
        }
    }

    #[test]
    fn count_three_has_no_duplicates_and_skips_seen() {
        let idx = index(3, 5, 6);
        let cfg = Config::default();
        let seen: Vec<String> = (0..5).map(|i| format!("d0-{i}")).collect();
        for seed in 0..100 {
            let r = run(&idx, &cfg, 10, &seen, &[], 3, seed);
            assert_eq!(r.picks.len(), 3);
            let ids: HashSet<&str> = r.picks.iter().map(|p| p.video_id.as_str()).collect();
            assert_eq!(ids.len(), 3);
            assert!(ids.iter().all(|id| !seen.iter().any(|s| s == id)));
        }
    }

    #[test]
    fn picks_in_one_call_respect_the_streak_limit() {
        let idx = index(3, 30, 8);
        let cfg = Config::default();
        for seed in 0..200 {
            let r = run(
                &idx,
                &cfg,
                10,
                &["x".into()],
                &["ds0".into(), "ds0".into()],
                3,
                seed,
            );
            let first = ds_of(&idx, &r.picks[0].video_id);
            assert_ne!(first, "ds0");
        }
    }

    #[test]
    fn all_seen_resets() {
        let idx = index(2, 3, 9);
        let cfg = Config::default();
        let seen: Vec<String> = idx.videos().iter().map(|v| v.id.clone()).collect();
        let r = run(&idx, &cfg, 10, &seen, &[], 2, 1);
        assert!(r.seen_reset);
        assert_eq!(r.picks.len(), 2);
        assert_ne!(r.picks[0].reason, Reason::First);
    }

    #[test]
    fn returns_fewer_when_candidates_run_out() {
        let idx = index(1, 2, 9);
        let r = run(&idx, &Config::default(), 10, &["d0-0".into()], &[], 3, 1);
        assert_eq!(r.picks.len(), 1);
        assert!(!r.seen_reset);
    }

    #[test]
    fn same_seed_same_result() {
        let idx = index(4, 50, 7);
        let cfg = Config::default();
        let a = run(&idx, &cfg, 5, &["x".into()], &[], 3, 123);
        let b = run(&idx, &cfg, 5, &["x".into()], &[], 3, 123);
        assert_eq!(a, b);
    }

    #[test]
    fn empty_index_is_an_error() {
        let idx = Index::new(vec![], vec![]);
        let r = pick_next(
            &idx,
            &Config::default(),
            &[1.0],
            0,
            &[],
            &[],
            1,
            &mut Rng::new(1),
        );
        assert_eq!(r, Err(EmptyIndex));
    }

    #[test]
    fn reason_serializes_as_snake_case() {
        assert_eq!(
            serde_json::to_string(&Reason::ExploreCold).unwrap(),
            "\"explore_cold\""
        );
    }
}
