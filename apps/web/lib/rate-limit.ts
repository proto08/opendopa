// レート制限(設計書 §6.5): 匿名 ID ごとに 1 秒あたり 10 リクエスト。
// インメモリのトークンバケット。レプリカ(最大 3)ごとに数えるので、レプリカ間では厳密にならない。

export const RATE_LIMIT_PER_SEC = 10;
const IDLE_MS = 60_000;
const SWEEP_EVERY = 1000;

interface Bucket {
  tokens: number;
  updatedAt: number;
}

export class RateLimiter {
  private buckets = new Map<string, Bucket>();
  private calls = 0;

  constructor(
    private readonly perSec: number = RATE_LIMIT_PER_SEC,
    private readonly now: () => number = Date.now,
  ) {}

  /** 1 リクエスト分を消費できれば true、制限を超えていれば false。 */
  allow(key: string): boolean {
    const t = this.now();
    if (++this.calls % SWEEP_EVERY === 0) this.sweep(t);
    const b = this.buckets.get(key) ?? { tokens: this.perSec, updatedAt: t };
    b.tokens = Math.min(this.perSec, b.tokens + ((t - b.updatedAt) / 1000) * this.perSec);
    b.updatedAt = t;
    const ok = b.tokens >= 1;
    if (ok) b.tokens -= 1;
    this.buckets.set(key, b);
    return ok;
  }

  // 使われなくなった匿名 ID の分を捨てて、メモリが増え続けないようにする。
  private sweep(t: number): void {
    for (const [k, b] of this.buckets) {
      if (t - b.updatedAt > IDLE_MS) this.buckets.delete(k);
    }
  }
}

export const rateLimiter = new RateLimiter();
