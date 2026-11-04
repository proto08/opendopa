//! 設計書 §7.1 の定数をここにまとめる(M4a で追加する)。

/// 埋め込みの次元(設計書 §5、`EMBED_DIM`)。
pub const EMBED_DIM: usize = 1024;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embed_dim_matches_design_doc() {
        assert_eq!(EMBED_DIM, 1024);
    }
}
