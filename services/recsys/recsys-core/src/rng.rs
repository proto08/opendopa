//! 乱数。テストで再現できるよう、`seed` から決まる小さな RNG(SplitMix64)を自前で持つ。
//! 暗号用途ではない。依存を増やさないために `rand` は使わない。

#[derive(Debug, Clone)]
pub struct Rng {
    state: u64,
}

impl Rng {
    pub fn new(seed: u64) -> Self {
        Self { state: seed }
    }

    pub fn next_u64(&mut self) -> u64 {
        self.state = self.state.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.state;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// 0 以上 1 未満の一様乱数。
    pub fn next_f64(&mut self) -> f64 {
        // 上位 53 ビットを使う。
        (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64
    }

    /// 0 以上 `n` 未満の整数。`n` は 1 以上。
    pub fn below(&mut self, n: usize) -> usize {
        debug_assert!(n > 0);
        ((self.next_f64() * n as f64) as usize).min(n.saturating_sub(1))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_seed_same_sequence() {
        let mut a = Rng::new(7);
        let mut b = Rng::new(7);
        for _ in 0..10 {
            assert_eq!(a.next_u64(), b.next_u64());
        }
    }

    #[test]
    fn values_stay_in_range() {
        let mut r = Rng::new(1);
        for _ in 0..1000 {
            let f = r.next_f64();
            assert!((0.0..1.0).contains(&f));
            assert!(r.below(5) < 5);
        }
    }
}
