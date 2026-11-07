import { describe, expect, it } from "vitest";
import { RateLimiter } from "./rate-limit";

describe("RateLimiter", () => {
  it("1 秒に 10 回までは通り、11 回目は拒否する", () => {
    const rl = new RateLimiter(10, () => 1000);
    for (let i = 0; i < 10; i++) expect(rl.allow("a")).toBe(true);
    expect(rl.allow("a")).toBe(false);
  });

  it("匿名 ID ごとに数える", () => {
    const rl = new RateLimiter(10, () => 1000);
    for (let i = 0; i < 10; i++) rl.allow("a");
    expect(rl.allow("b")).toBe(true);
  });

  it("時間が経つと回復する", () => {
    let t = 0;
    const rl = new RateLimiter(10, () => t);
    for (let i = 0; i < 10; i++) rl.allow("a");
    expect(rl.allow("a")).toBe(false);
    t = 100; // 0.1 秒で 1 トークン
    expect(rl.allow("a")).toBe(true);
    expect(rl.allow("a")).toBe(false);
  });
});
