//! 好みのベクトル `u` の再生(設計書 §7.2、§7.3)。`u` は保存せず、`events` から毎回作る。

use std::collections::HashMap;

use serde::Deserialize;

use crate::{config::Config, index::Index};

/// 視聴・いいねのイベント。JSON の形は設計書 §6.6。
#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum Event {
    #[serde(rename_all = "camelCase")]
    View { video_id: String, ratio: f32 },
    #[serde(rename_all = "camelCase")]
    Like { video_id: String, liked: bool },
}

/// 再生の結果。`skipped` は無視したイベントの説明(呼び出し側が警告として出す)。
#[derive(Debug, Clone, PartialEq)]
pub struct Replay {
    pub u: Vec<f32>,
    pub skipped: Vec<String>,
}

/// 内積。次元が違う分は切り捨てられる(`Index` が同じ次元を保証する前提)。
pub fn dot(a: &[f32], b: &[f32]) -> f32 {
    a.iter().zip(b).map(|(a, b)| a * b).sum()
}

/// ベクトルを長さ 1 にする。長さが 0(または非有限)なら `None`。
pub fn normalize(v: &[f32]) -> Option<Vec<f32>> {
    let norm = v.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm.is_finite() && norm > 1e-12 {
        Some(v.iter().map(|x| x / norm).collect())
    } else {
        None
    }
}

/// `u = normalize(u + a * (v - u))`。結果がゼロベクトルになるときは `u` を変えない。
fn step(u: &[f32], v: &[f32], a: f32) -> Vec<f32> {
    // 次元の食い違いは zip が黙って切り詰めるので、開発中に気づけるようにする。
    debug_assert_eq!(u.len(), v.len(), "u と v の次元が違う");
    let moved: Vec<f32> = u.iter().zip(v).map(|(u, v)| u + a * (v - u)).collect();
    normalize(&moved).unwrap_or_else(|| u.to_vec())
}

/// 視聴率 `ratio` から、更新の係数 `a` を求める(§7.2)。
pub fn view_coefficient(ratio: f32, config: &Config) -> f32 {
    let r = ratio.clamp(0.0, 1.0);
    let w = ((r - config.watch_neutral) / (1.0 - config.watch_neutral)).clamp(-1.0, 1.0);
    if w >= 0.0 {
        config.alpha_pos * w
    } else {
        config.alpha_neg * w
    }
}

/// `u0` から `events` を先頭から順に再生して `u` を作る。
///
/// - `view` は届いた順に毎回適用する。
/// - `like` は、動画ごとに**最後の `like` の位置**でだけ見る。そこが `liked=true` なら
///   その位置で 1 回適用し、`liked=false` なら何もしない(取り消し)。それ以前の `like` は無視する。
/// - 索引にない `videoId` と、`ratio` が数でないイベントは無視し、`skipped` に残す。
pub fn replay_with_report(u0: &[f32], events: &[Event], index: &Index, config: &Config) -> Replay {
    let mut last_like: HashMap<&str, usize> = HashMap::new();
    for (i, e) in events.iter().enumerate() {
        if let Event::Like { video_id, .. } = e {
            last_like.insert(video_id, i);
        }
    }

    let mut u = normalize(u0).unwrap_or_else(|| u0.to_vec());
    let mut skipped = Vec::new();
    for (i, e) in events.iter().enumerate() {
        match e {
            Event::View { video_id, ratio } => {
                let Some(video) = index.video(video_id) else {
                    skipped.push(format!("索引にない videoId の view を無視: {video_id}"));
                    continue;
                };
                if !ratio.is_finite() {
                    skipped.push(format!("ratio が数でない view を無視: {video_id}"));
                    continue;
                }
                u = step(&u, &video.vector, view_coefficient(*ratio, config));
            }
            Event::Like { video_id, liked } => {
                if last_like.get(video_id.as_str()) != Some(&i) {
                    continue;
                }
                let Some(video) = index.video(video_id) else {
                    skipped.push(format!("索引にない videoId の like を無視: {video_id}"));
                    continue;
                };
                if *liked {
                    u = step(&u, &video.vector, config.alpha_like);
                }
            }
        }
    }
    Replay { u, skipped }
}

/// `replay_with_report` の `u` だけを返す。
pub fn replay(u0: &[f32], events: &[Event], index: &Index, config: &Config) -> Vec<f32> {
    replay_with_report(u0, events, index, config).u
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::index::Video;

    fn video(id: &str, v: &[f32]) -> Video {
        Video {
            id: id.into(),
            dataset_id: "d".into(),
            vector: normalize(v).unwrap(),
            x: 0.0,
            y: 0.0,
        }
    }

    fn index() -> Index {
        Index::new(
            vec![video("a", &[1.0, 0.0, 0.0]), video("b", &[0.0, 1.0, 0.0])],
            vec![],
        )
    }

    fn view(id: &str, ratio: f32) -> Event {
        Event::View {
            video_id: id.into(),
            ratio,
        }
    }

    fn like(id: &str, liked: bool) -> Event {
        Event::Like {
            video_id: id.into(),
            liked,
        }
    }

    const U0: [f32; 3] = [0.0, 0.0, 1.0];

    fn close(a: &[f32], b: &[f32]) -> bool {
        a.iter().zip(b).all(|(x, y)| (x - y).abs() < 1e-6)
    }

    fn norm(v: &[f32]) -> f32 {
        v.iter().map(|x| x * x).sum::<f32>().sqrt()
    }

    #[test]
    fn coefficients_match_spec() {
        let c = Config::default();
        assert!((view_coefficient(1.0, &c) - 0.5).abs() < 1e-6);
        assert!((view_coefficient(0.0, &c) + 0.2).abs() < 1e-6);
        assert!(view_coefficient(0.4, &c).abs() < 1e-6);
        assert!((view_coefficient(2.0, &c) - 0.5).abs() < 1e-6);
    }

    #[test]
    fn full_watch_moves_toward_video() {
        let c = Config::default();
        let u = replay(&U0, &[view("a", 1.0)], &index(), &c);
        // u0 + 0.5*(v-u0) = (0.5, 0, 0.5) を正規化
        let s = 0.5_f32.hypot(0.5);
        assert!(close(&u, &[0.5 / s, 0.0, 0.5 / s]));
        assert!((norm(&u) - 1.0).abs() < 1e-6);
    }

    #[test]
    fn skip_moves_away_and_neutral_keeps() {
        let c = Config::default();
        let u = replay(&U0, &[view("a", 0.0)], &index(), &c);
        assert!(u[0] < 0.0);
        assert!((norm(&u) - 1.0).abs() < 1e-6);
        assert!(close(&replay(&U0, &[view("a", 0.4)], &index(), &c), &U0));
    }

    #[test]
    fn unlike_equals_never_liked() {
        let c = Config::default();
        let idx = index();
        let with = [
            view("a", 0.8),
            like("b", true),
            view("b", 0.2),
            like("b", false),
        ];
        let without = [view("a", 0.8), view("b", 0.2)];
        assert!(close(
            &replay(&U0, &with, &idx, &c),
            &replay(&U0, &without, &idx, &c)
        ));
    }

    #[test]
    fn like_unlike_like_is_one_like_at_last_position() {
        let c = Config::default();
        let idx = index();
        let flip = [
            like("a", true),
            view("b", 1.0),
            like("a", false),
            like("a", true),
        ];
        let once = [view("b", 1.0), like("a", true)];
        let u = replay(&U0, &flip, &idx, &c);
        assert!(close(&u, &replay(&U0, &once, &idx, &c)));
        assert!(!close(&u, &replay(&U0, &[view("b", 1.0)], &idx, &c)));
    }

    #[test]
    fn deterministic() {
        let c = Config::default();
        let ev = [view("a", 0.9), like("b", true), view("b", 0.1)];
        assert_eq!(
            replay(&U0, &ev, &index(), &c),
            replay(&U0, &ev, &index(), &c)
        );
    }

    #[test]
    fn config_changes_result() {
        let ev = [view("a", 1.0)];
        let base = replay(&U0, &ev, &index(), &Config::default());
        let c = Config {
            alpha_pos: 0.9,
            ..Config::default()
        };
        assert!(!close(&base, &replay(&U0, &ev, &index(), &c)));
    }

    #[test]
    fn unknown_video_is_skipped_with_report() {
        let c = Config::default();
        let r = replay_with_report(
            &U0,
            &[view("zzz", 1.0), like("zzz", true), view("a", f32::NAN)],
            &index(),
            &c,
        );
        assert!(close(&r.u, &U0));
        assert_eq!(r.skipped.len(), 3);
    }

    #[test]
    fn zero_vector_is_guarded() {
        assert_eq!(normalize(&[0.0, 0.0]), None);
        // u と v が正反対で a=0.5 だと u + a*(v-u) がゼロになる → u を変えない
        let u = step(&[1.0, 0.0], &[-1.0, 0.0], 0.5);
        assert_eq!(u, vec![1.0, 0.0]);
    }

    #[test]
    #[should_panic(expected = "次元が違う")]
    #[cfg(debug_assertions)]
    fn step_rejects_dimension_mismatch() {
        step(&[1.0, 0.0], &[1.0, 0.0, 0.0], 0.5);
    }

    #[test]
    fn parses_event_json() {
        let ev: Vec<Event> = serde_json::from_str(
            r#"[{"type":"view","videoId":"a","ratio":0.72},{"type":"like","videoId":"a","liked":false}]"#,
        )
        .unwrap();
        assert_eq!(ev, vec![view("a", 0.72), like("a", false)]);
    }
}
