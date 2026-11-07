//! 設計書 §7.1 の定数をここにまとめる。値は設定ファイル(TOML)から読み込める。

use std::{fmt, fs, io, path::Path};

use serde::Deserialize;

/// 埋め込みの次元(設計書 §5、`EMBED_DIM`)。
pub const EMBED_DIM: usize = 1024;

/// 設計書 §7.1 の定数。TOML のキーは小文字のスネークケース(`watch_neutral` など)。
/// 書かれていない項目は既定値になる。未知のキーはエラーにする(綴りの誤りに気づくため)。
#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Config {
    /// この視聴率が「普通」。これより長ければ好き、短ければ嫌い。
    pub watch_neutral: f32,
    /// 視聴率 100% のときに、好みを動画へ近づける量。
    pub alpha_pos: f32,
    /// 視聴率 0% のときに、好みを動画から遠ざける量。
    pub alpha_neg: f32,
    /// いいねで近づける量。
    pub alpha_like: f32,
    /// 近傍候補の数。
    pub topk: usize,
    /// 候補から確率で選ぶときの温度。
    pub tau: f32,
    /// 冒険枠の確率。
    pub explore: f32,
    /// 最初の N 本は、全データセットから偏らず選ぶ。
    pub cold_start_n: usize,
    /// `discover_n` 本目までは、まだ出ていないデータセットが残っている間、新しいデータセットから選ぶ
    /// (好みの信号がない利用者でも、全データセットを一巡して好みを見つけるため)。`cold_start_n` 以下なら無効。
    pub discover_n: usize,
    /// 同じデータセットが連続できる最大数。
    pub max_streak: usize,
    /// 地図上の現在地を出すときの温度。
    pub tau_map: f32,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            watch_neutral: 0.4,
            alpha_pos: 0.5,
            alpha_neg: 0.3,
            alpha_like: 0.6,
            topk: 20,
            tau: 0.05,
            explore: 0.18,
            cold_start_n: 3,
            discover_n: 14,
            max_streak: 3,
            tau_map: 0.05,
        }
    }
}

/// 設定の読み込みや検証の失敗。
#[derive(Debug)]
pub enum ConfigError {
    Io(io::Error),
    Parse(toml::de::Error),
    /// 値が使えない範囲にある。
    Invalid(String),
}

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(e) => write!(f, "設定ファイルを読めません: {e}"),
            Self::Parse(e) => write!(f, "設定ファイルの形式が正しくありません: {e}"),
            Self::Invalid(m) => write!(f, "設定の値が正しくありません: {m}"),
        }
    }
}

impl std::error::Error for ConfigError {}

impl Config {
    /// TOML の文字列から読み込み、値を検証する。
    pub fn from_toml_str(s: &str) -> Result<Self, ConfigError> {
        let config: Self = toml::from_str(s).map_err(ConfigError::Parse)?;
        config.validate()?;
        Ok(config)
    }

    /// TOML ファイルから読み込む。
    pub fn from_file(path: impl AsRef<Path>) -> Result<Self, ConfigError> {
        let s = fs::read_to_string(path).map_err(ConfigError::Io)?;
        Self::from_toml_str(&s)
    }

    /// 計算が破綻する値(0 除算、確率の範囲外など)を弾く。
    pub fn validate(&self) -> Result<(), ConfigError> {
        let bad = |m: &str| Err(ConfigError::Invalid(m.to_string()));
        if !(0.0..1.0).contains(&self.watch_neutral) {
            return bad("watch_neutral は 0 以上 1 未満");
        }
        for (name, v) in [
            ("alpha_pos", self.alpha_pos),
            ("alpha_neg", self.alpha_neg),
            ("alpha_like", self.alpha_like),
        ] {
            if !(0.0..=1.0).contains(&v) {
                return bad(&format!("{name} は 0 以上 1 以下"));
            }
        }
        if !(0.0..=1.0).contains(&self.explore) {
            return bad("explore は 0 以上 1 以下");
        }
        if self.tau <= 0.0
            || self.tau_map <= 0.0
            || !self.tau.is_finite()
            || !self.tau_map.is_finite()
        {
            return bad("tau と tau_map は正の数");
        }
        if self.topk == 0 || self.max_streak == 0 {
            return bad("topk と max_streak は 1 以上");
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embed_dim_matches_design_doc() {
        assert_eq!(EMBED_DIM, 1024);
    }

    #[test]
    fn bundled_file_matches_defaults() {
        let c = Config::from_toml_str(include_str!("../../config/recsys.toml")).unwrap();
        assert_eq!(c, Config::default());
    }

    #[test]
    fn partial_file_fills_defaults() {
        let c = Config::from_toml_str("alpha_pos = 0.9").unwrap();
        assert_eq!(c.alpha_pos, 0.9);
        assert_eq!(c.alpha_neg, 0.3);
    }

    #[test]
    fn rejects_unknown_key_and_bad_values() {
        assert!(Config::from_toml_str("alpha_posu = 0.9").is_err());
        assert!(Config::from_toml_str("tau = 0").is_err());
        assert!(Config::from_toml_str("watch_neutral = 1.0").is_err());
        assert!(Config::from_toml_str("topk = 0").is_err());
    }
}
