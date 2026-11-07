//! 疑似ユーザーのシミュレーションと性能の確認(Issue #42、設計書 §7.1、§13 M4a、§14.1、§14.2)。
//!
//! 合成インデックス(14 データセット × 150 本 × 1024 次元)に対し、好みが決まった疑似ユーザーを
//! 100 本ぶん動かして、好みのデータセットが配信の累計の過半数を超える本数を測る。
//! 乱数はすべて `seed` から決まるので、結果は再現できる。

use std::{collections::HashMap, time::Instant};

use recsys_core::{
    config::{Config, EMBED_DIM},
    index::{Index, Video},
    panel::taste_position,
    pick::{Reason, pick_next},
    rng::Rng,
    taste::{Event, normalize, replay},
};

const DATASETS: usize = 14;
const PER_DATASET: usize = 150;
const STEPS: usize = 100;
/// 受け入れ条件: この本数以内に、好みが累計の過半数を超える。
const LIMIT: usize = 20;

/// 目標: 初出と一巡のあとの LIMIT 本のうち、好みの本数の平均がこの割合以上(連続は 3 本まで、冒険枠は約 18%)。
const TARGET_SHARE: f64 = 0.65;

/// 標準正規分布に近い乱数(一様乱数 12 個の和 - 6)。
fn gauss(rng: &mut Rng) -> f32 {
    ((0..12).map(|_| rng.next_f64()).sum::<f64>() - 6.0) as f32
}

fn random_unit(rng: &mut Rng) -> Vec<f32> {
    let v: Vec<f32> = (0..EMBED_DIM).map(|_| gauss(rng)).collect();
    normalize(&v).unwrap()
}

/// データセットごとに近い塊になる合成インデックス。
/// 動画 = normalize(データセットの中心 + 0.5 * ノイズ)。地図の座標は、データセットごとに円周上へ置き、少しずらす。
/// 動画 ID は `<dataset>_<番号>`、データセット ID は 0 番目が `rail_*`、1 番目が `akiya_*`(以降は `dsN`)。
fn synthetic_index(seed: u64) -> Index {
    let mut rng = Rng::new(seed);
    let names: Vec<String> = (0..DATASETS)
        .map(|d| match d {
            0 => "rail".to_string(),
            1 => "akiya".to_string(),
            d => format!("ds{d}"),
        })
        .collect();
    let mut videos = Vec::with_capacity(DATASETS * PER_DATASET);
    for (d, name) in names.iter().enumerate() {
        let center = random_unit(&mut rng);
        let angle = d as f64 / DATASETS as f64 * std::f64::consts::TAU;
        let (cx, cy) = (0.5 + 0.4 * angle.cos(), 0.5 + 0.4 * angle.sin());
        for n in 0..PER_DATASET {
            let noisy: Vec<f32> = center
                .iter()
                .map(|c| c + 0.5 * gauss(&mut rng) / (EMBED_DIM as f32).sqrt())
                .collect();
            videos.push(Video {
                id: format!("{name}_{n:03}"),
                dataset_id: name.clone(),
                vector: normalize(&noisy).unwrap(),
                x: cx as f32 + 0.03 * (rng.next_f64() as f32 - 0.5),
                y: cy as f32 + 0.03 * (rng.next_f64() as f32 - 0.5),
            });
        }
    }
    Index::new(videos, vec![])
}

/// 全動画の重心(長さ 1)。好みの初期値 `u0`(設計書 §7.2)。
fn centroid(index: &Index) -> Vec<f32> {
    let mut sum = vec![0.0f32; EMBED_DIM];
    for v in index.videos() {
        for (s, x) in sum.iter_mut().zip(&v.vector) {
            *s += x;
        }
    }
    normalize(&sum).unwrap()
}

#[derive(Clone, Copy)]
enum User {
    /// 好みのデータセットは最後まで見る(1.0)。他はすぐ飛ばす(0.05)。
    Watcher,
    /// 好みのデータセットにいいねを押す。他は普通(0.5)。
    Liker,
}

struct Outcome {
    /// 好みのデータセットが累計の過半数を超えた最初の本数(超えなければ `None`)。
    majority_at: Option<usize>,
    /// 好みのデータセットが初めて配信された本数。
    first_fav: Option<usize>,
    /// 初出と一巡(`discover_n` 本)の遅いほうの次の本から LIMIT 本ぶんのうち、好みだった本数
    /// (その本数が配信されていなければ `None`)。一巡のあいだは新しいデータセットを強制するので、数えない。
    fav_after_discovery: Option<usize>,
    /// 配信した STEPS 本のうち、好み以外の本数。
    off_taste: usize,
    adventures: usize,
}

fn simulate(index: &Index, config: &Config, user: User, favorite: &str, seed: u64) -> Outcome {
    let u0 = centroid(index);
    let mut rng = Rng::new(seed);
    let mut events: Vec<Event> = Vec::new();
    let mut seen: Vec<String> = Vec::new();
    let mut recent: Vec<String> = Vec::new(); // 新しい順
    let mut by_id: HashMap<&str, &str> = HashMap::new();
    for v in index.videos() {
        by_id.insert(&v.id, &v.dataset_id);
    }
    let (mut fav, mut majority_at, mut adventures) = (0usize, None, 0usize);
    let mut first_fav = None;
    let mut hits: Vec<bool> = Vec::new();
    let discover_n = config.discover_n;

    for n in 1..=STEPS {
        let u = replay(&u0, &events, index, config);
        let event_count = events
            .iter()
            .filter(|e| matches!(e, Event::View { .. }))
            .count();
        let result = pick_next(
            index,
            config,
            &u,
            event_count,
            &seen,
            &recent,
            1,
            None,
            &mut rng,
        )
        .unwrap();
        let pick = &result.picks[0];
        if pick.reason == Reason::Adventure {
            adventures += 1;
        }
        let dataset = by_id[pick.video_id.as_str()];
        let liked_it = dataset == favorite;
        if liked_it {
            fav += 1;
        }
        if liked_it && first_fav.is_none() {
            first_fav = Some(n);
        }
        hits.push(liked_it);
        if majority_at.is_none() && fav * 2 > n {
            majority_at = Some(n);
        }
        let (ratio, like) = match (user, liked_it) {
            (User::Watcher, true) => (1.0, false),
            (User::Watcher, false) => (0.05, false),
            (User::Liker, true) => (0.5, true),
            (User::Liker, false) => (0.5, false),
        };
        events.push(Event::View {
            video_id: pick.video_id.clone(),
            ratio,
        });
        if like {
            events.push(Event::Like {
                video_id: pick.video_id.clone(),
                liked: true,
            });
        }
        seen.push(pick.video_id.clone());
        recent.insert(0, dataset.to_string());
    }
    Outcome {
        majority_at,
        first_fav,
        fav_after_discovery: first_fav
            .map(|d| d.max(discover_n))
            .filter(|d| d + LIMIT <= STEPS)
            .map(|d| hits[d..d + LIMIT].iter().filter(|h| **h).count()),
        off_taste: STEPS - fav,
        adventures,
    }
}

/// `expect_found_within`: 好みの初出が、この本数以内であることを全 seed で求める(`None` なら求めない)。
fn check(user: User, favorite: &str, expect_found_within: Option<usize>) {
    let config = Config::default();
    let mut shares = Vec::new();
    for seed in 1..=10u64 {
        let index = synthetic_index(seed);
        let o = simulate(&index, &config, user, favorite, seed * 7919);
        println!(
            "seed {seed}: 初出 {:?} 本目 / 累計過半数 {:?} / 初出のあと{LIMIT}本中の好み {:?} / 好み以外 {} 本 / 冒険枠 {} 本",
            o.first_fav, o.majority_at, o.fav_after_discovery, o.off_taste, o.adventures
        );
        if let Some(limit) = expect_found_within {
            let at = o.first_fav.unwrap_or(usize::MAX);
            assert!(
                at <= limit,
                "seed {seed}: 好みの初出が {at} 本目(目安 {limit} 本以内)"
            );
        }
        // 好みを知ったあとの学習: 初出のあとの LIMIT 本で、好みが多数派に近い(連続制限と冒険枠があるので、全部は好みにならない)。
        if let Some(n) = o.fav_after_discovery {
            assert!(
                n * 5 >= LIMIT * 2,
                "seed {seed}: 初出のあとの {LIMIT} 本のうち好みは {n} 本しかない"
            );
            shares.push(n);
        }
        // 冒険枠が働いている: 好み以外が 1 割以上混ざる。
        assert!(
            o.off_taste >= STEPS / 10,
            "seed {seed}: 好み以外が {} 本しかない",
            o.off_taste
        );
        assert!(o.adventures > 0, "seed {seed}: 冒険枠が一度も出ていない");
    }
    assert!(!shares.is_empty(), "どの seed でも好みが一度も出なかった");
    let mean = shares.iter().sum::<usize>() as f64 / shares.len() as f64;
    println!("初出のあと{LIMIT}本中の好み 平均 {mean:.1} 本");
    assert!(
        mean >= LIMIT as f64 * TARGET_SHARE,
        "平均 {mean:.1} 本で、目標の {:.0}% に届かない",
        TARGET_SHARE * 100.0
    );
}

#[test]
fn user_a_watching_rail_converges() {
    check(User::Watcher, "rail", Some(LIMIT));
}

#[test]
fn user_b_liking_akiya_converges() {
    check(User::Liker, "akiya", Some(LIMIT));
}

/// 2,100 本 × 1024 次元での処理時間。debug ビルドでは意味がないので、通常は走らせない:
/// `cargo test --release -p recsys-core --test simulation -- --ignored --nocapture`
#[test]
#[ignore = "release ビルドで測る性能テスト"]
fn performance_pick_and_position() {
    let index = synthetic_index(1);
    assert_eq!(index.len(), DATASETS * PER_DATASET);
    let config = Config::default();
    let u = centroid(&index);
    let mut rng = Rng::new(1);
    let seen: Vec<String> = index
        .videos()
        .iter()
        .take(50)
        .map(|v| v.id.clone())
        .collect();
    let recent = vec!["rail".to_string()];

    const RUNS: u32 = 200;
    let t = Instant::now();
    for _ in 0..RUNS {
        pick_next(&index, &config, &u, 10, &seen, &recent, 3, None, &mut rng).unwrap();
    }
    let pick_ms = t.elapsed().as_secs_f64() * 1000.0 / RUNS as f64;

    let t = Instant::now();
    for _ in 0..RUNS {
        taste_position(&index, &config, &u).unwrap();
    }
    let pos_ms = t.elapsed().as_secs_f64() * 1000.0 / RUNS as f64;

    println!("pick_next(count=3): {pick_ms:.3} ms / taste_position: {pos_ms:.3} ms");
    // 目安は「数 ms 以内」。実行環境のばらつきを見込んで 10 ms で失敗にする。
    assert!(pick_ms < 10.0 && pos_ms < 10.0);
}

/// 定数を調整するときの探索用。seed 1〜30 で、過半数に達した本数・好みの初出・初出のあとの好み率を出す。
/// `cargo test --release -p recsys-core --test simulation sweep -- --ignored --nocapture`
#[test]
#[ignore = "定数調整用の探索。結果を出力するだけ"]
fn sweep() {
    let base = Config::default();
    let variants: Vec<(&str, Config)> = vec![
        ("既定", base.clone()),
        (
            "discover_n=3(#119 より前)",
            Config {
                discover_n: 3,
                ..base.clone()
            },
        ),
        (
            "max_streak=3",
            Config {
                max_streak: 3,
                ..base.clone()
            },
        ),
        (
            "max_streak=4",
            Config {
                max_streak: 4,
                ..base.clone()
            },
        ),
        (
            "explore=0.12",
            Config {
                explore: 0.12,
                ..base.clone()
            },
        ),
        (
            "max_streak=3 explore=0.12",
            Config {
                max_streak: 3,
                explore: 0.12,
                ..base.clone()
            },
        ),
    ];
    for (name, config) in variants {
        for (label, user, fav) in [("A", User::Watcher, "rail"), ("B", User::Liker, "akiya")] {
            let outs: Vec<Outcome> = (1..=30u64)
                .map(|s| simulate(&synthetic_index(s), &config, user, fav, s * 7919))
                .collect();
            let stat = |f: &dyn Fn(&Outcome) -> Option<usize>| {
                let mut v: Vec<usize> = outs.iter().map(|o| f(o).unwrap_or(999)).collect();
                v.sort();
                format!(
                    "{LIMIT} 本以内 {}/30 中央値 {} (999=100 本では届かず)",
                    v.iter().filter(|&&a| a <= LIMIT).count(),
                    v[15]
                )
            };
            let after: Vec<usize> = outs.iter().filter_map(|o| o.fav_after_discovery).collect();
            let mean = after.iter().sum::<usize>() as f64 / after.len().max(1) as f64;
            println!(
                "{name} {label}: 累計過半数 {} / 好みの初出 {} / 初出のあと{LIMIT}本中の好み 平均 {mean:.1} 本",
                stat(&|o| o.majority_at),
                stat(&|o| o.first_fav),
            );
        }
    }
}

/// 候補が数本のときの動き(Issue #153)。候補は rail 3 本・akiya 2 本。疑似ユーザーは rail を最後まで見る。
/// 候補の外は出ず、一巡するまで重複せず、一巡したら `seen_reset` になる。
#[test]
fn few_candidates_discovery_streak_and_reset() {
    let config = Config::default();
    let candidates: Vec<String> = ["rail_000", "rail_001", "rail_002", "akiya_000", "akiya_001"]
        .map(String::from)
        .to_vec();
    for seed in 1..=10u64 {
        let index = synthetic_index(seed);
        let u0 = centroid(&index);
        let mut rng = Rng::new(seed * 31);
        let (mut events, mut seen, mut recent) = (Vec::new(), Vec::<String>::new(), Vec::new());
        let mut log = Vec::new();
        let mut resets = 0;
        for n in 0..15 {
            let u = replay(&u0, &events, &index, &config);
            let r = pick_next(
                &index,
                &config,
                &u,
                n,
                &seen,
                &recent,
                1,
                Some(&candidates),
                &mut rng,
            )
            .unwrap();
            assert!(!r.pool_empty);
            let pick = &r.picks[0];
            assert!(candidates.contains(&pick.video_id), "候補の外が選ばれた");
            if r.seen_reset {
                resets += 1;
                assert_eq!(seen.len(), candidates.len(), "全部見たときだけリセット");
                seen.clear();
            }
            assert!(!seen.contains(&pick.video_id), "一巡の間は重複しない");
            let dataset = index.video(&pick.video_id).unwrap().dataset_id.clone();
            let ratio = if dataset == "rail" { 1.0 } else { 0.05 };
            events.push(Event::View {
                video_id: pick.video_id.clone(),
                ratio,
            });
            seen.push(pick.video_id.clone());
            recent.insert(0, dataset);
            log.push(format!("{}:{:?}", pick.video_id, pick.reason));
        }
        println!("seed {seed}: リセット {resets} 回 / {}", log.join(" "));
        assert_eq!(resets, 2, "15 本 = 5 本 x 3 周で、2 回リセット");
        // 発見: 最初の 2 本は別のデータセット(rail と akiya の両方が出る)。
        let first_two: Vec<&str> = log[..2].iter().map(|s| &s[..4]).collect();
        assert!(
            first_two.contains(&"rail") && first_two.contains(&"akiy"),
            "seed {seed}: 最初の 2 本で両方のデータセットが出る: {first_two:?}"
        );
    }
}
