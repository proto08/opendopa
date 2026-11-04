//! recsys の計算の核(ADR-0012 A6)。
//!
//! 好みのベクトルの更新、次の動画の選択、割合の計算など、設計書 §7 の計算をここに書く(M4a)。
//! この crate は HTTP・DB・非同期ランタイムに依存しない。依存を足すときは、
//! 純粋な計算のためのものに限る(axum・sqlx・tokio などは recsys-server 側に置く)。

pub mod config;
