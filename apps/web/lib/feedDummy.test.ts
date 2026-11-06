import { validateScene } from "@opendopa/shared";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/server", () => ({ connection: vi.fn(async () => {}) }));

import { GET } from "@/app/api/feed/route";
import { fixtureItems, parseCount, pickRandom } from "./feedDummy";
import type { FeedResponse } from "./feedTypes";

describe("parseCount", () => {
  it("1〜3 に丸め、不正なら 1", () => {
    expect(parseCount("2")).toBe(2);
    expect(parseCount("9")).toBe(3);
    expect(parseCount("0")).toBe(1);
    expect(parseCount(null)).toBe(1);
    expect(parseCount("x")).toBe(1);
  });
});

describe("pickRandom", () => {
  it("重複なしで n 件。足りなければ繰り返す", () => {
    expect(new Set(pickRandom([1, 2, 3], 3)).size).toBe(3);
    expect(pickRandom([1, 2], 5)).toHaveLength(5);
    expect(pickRandom([], 2)).toEqual([]);
  });
});

describe("GET /api/feed(ダミー)", () => {
  it("items[] が本物と同じ形で、scene がスキーマを満たす", async () => {
    const prev = process.env.DATABASE_URL;
    delete process.env.DATABASE_URL; // DB なし → フィクスチャ
    try {
      const res = await GET(new Request("http://localhost/api/feed?count=2"));
      expect(res.headers.get("Cache-Control")).toBe("no-store");
      const body = (await res.json()) as FeedResponse;
      expect(body.items).toHaveLength(2);
      for (const item of body.items) {
        expect(Object.keys(item).sort()).toEqual(
          ["csvRow", "reason", "reasonLabel", "scene", "sourceRef", "videoId"].sort(),
        );
        expect(item.videoId).toBe(item.scene.videoId);
        expect(validateScene(item.scene).ok).toBe(true);
      }
    } finally {
      if (prev !== undefined) process.env.DATABASE_URL = prev;
    }
  });

  it("フィクスチャは 4 本", () => {
    expect(fixtureItems()).toHaveLength(4);
  });
});
