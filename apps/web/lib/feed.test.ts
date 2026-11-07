import { describe, expect, it, vi } from "vitest";
import { type FeedDeps, feedQuery, getFeed } from "./feed";
import type { HttpError } from "./http";
import type { VideoRow } from "./queries/videos";

const scene = (id: string) => ({
  videoId: id,
  headline: `h-${id}`,
  numbers: [{ secret: 1 }],
});
const video = (id: string): VideoRow => ({
  id,
  headline: `h-${id}`,
  scene: scene(id),
  csvRow: [["列", "値"]],
  sourceRef: "行 #1",
});

function makeDeps(over: Partial<FeedDeps> = {}): FeedDeps {
  return {
    loadEvents: async () => [{ type: "view", videoId: "a", ratio: 1 }],
    loadImpressions: async () => ({ seenIds: ["a"], recentDatasets: ["d1"] }),
    recsysFeed: async () => ({
      picks: [
        { videoId: "b", reason: "near" },
        { videoId: "c", reason: "adventure" },
      ],
      taste: { x: 0.1, y: 0.2, shares: [{ clusterId: 1, pct: 100 }] },
    }),
    loadVideos: async (ids) => new Map(ids.map((i) => [i, video(i)])),
    recordImpressions: async () => {},
    loadKnownTagIds: async (ids) => new Set(ids.filter((i) => i !== "bad:x")),
    loadVideoIdsWithAllTags: async () => ["b", "c"],
    loadClusters: async () => [
      { id: 1, name: "ドローン", color: "#FF0000", cx: 0.1, cy: 0.2 },
    ],
    loadMapPoints: async () => [
      { videoId: "b", datasetId: "d1", x: 0.1, y: 0.2, clusterId: 1 },
    ],
    loadViewLog: async () => [],
    countViews: async () => 1,
    ...over,
  };
}

describe("feedQuery", () => {
  const parse = (q: Record<string, string>) => feedQuery.safeParse(q);
  it("既定は count=1、includeMap=0", () => {
    expect(parse({})).toMatchObject({
      success: true,
      data: { count: 1, includeMap: "0" },
    });
  });
  it("count は 1〜3。0 と 4 は外れる", () => {
    expect(parse({ count: "3" }).success).toBe(true);
    expect(parse({ count: "0" }).success).toBe(false);
    expect(parse({ count: "4" }).success).toBe(false);
    expect(parse({ count: "x" }).success).toBe(false);
    expect(parse({ count: "1.5" }).success).toBe(false);
  });
  it("includeMap は 0 か 1", () => {
    expect(parse({ includeMap: "1" }).success).toBe(true);
    expect(parse({ includeMap: "2" }).success).toBe(false);
  });
});

describe("feedQuery の tag", () => {
  const parse = (q: Record<string, string | string[]>) =>
    feedQuery.safeParse(q);
  it("なければ空配列。1 個は文字列でも配列でもよく、重複は除く", () => {
    expect(parse({})).toMatchObject({ success: true, data: { tag: [] } });
    expect(parse({ tag: "a:1" })).toMatchObject({ data: { tag: ["a:1"] } });
    expect(parse({ tag: ["a:1", "b:2", "a:1"] })).toMatchObject({
      data: { tag: ["a:1", "b:2"] },
    });
  });
  it("4 個までは通り、5 個は外れる。空文字も外れる", () => {
    expect(parse({ tag: ["a", "b", "c", "d"] }).success).toBe(true);
    expect(parse({ tag: ["a", "b", "c", "d", "e"] }).success).toBe(false);
    expect(parse({ tag: "" }).success).toBe(false);
  });
});

describe("getFeed(タグの絞り込み)", () => {
  it("タグがなければ candidateIds を渡さず、タグ用の問い合わせもしない", async () => {
    const recsysFeed = vi.fn(makeDeps().recsysFeed);
    const loadVideoIdsWithAllTags = vi.fn(async () => ["x"]);
    const recordImpressions = vi.fn(async () => {});
    const res = await getFeed(
      makeDeps({ recsysFeed, loadVideoIdsWithAllTags, recordImpressions }),
      "u1",
      1,
      false,
      [],
    );
    expect(recsysFeed.mock.calls[0][0]).not.toHaveProperty("candidateIds");
    expect(loadVideoIdsWithAllTags).not.toHaveBeenCalled();
    expect(recordImpressions.mock.calls[0]).toHaveLength(3);
    expect(res).not.toHaveProperty("reason");
  });

  it("AND で引いた動画 ID を candidateIds として渡す", async () => {
    const recsysFeed = vi.fn(makeDeps().recsysFeed);
    const loadVideoIdsWithAllTags = vi.fn(async () => ["b", "c"]);
    await getFeed(
      makeDeps({ recsysFeed, loadVideoIdsWithAllTags }),
      "u1",
      2,
      false,
      ["dataset:rental", "region:hokkaido"],
    );
    expect(loadVideoIdsWithAllTags).toHaveBeenCalledWith([
      "dataset:rental",
      "region:hokkaido",
    ]);
    expect(recsysFeed.mock.calls[0][0]).toMatchObject({
      candidateIds: ["b", "c"],
    });
  });

  it("未知のタグは 400(recsys は呼ばない)", async () => {
    const recsysFeed = vi.fn(makeDeps().recsysFeed);
    await expect(
      getFeed(makeDeps({ recsysFeed }), "u1", 1, false, [
        "dataset:rental",
        "bad:x",
      ]),
    ).rejects.toMatchObject({ status: 400 });
    expect(recsysFeed).not.toHaveBeenCalled();
  });

  it("候補が尽きたら items: [] と reason: pool_empty(taste は返し、配信は記録しない)", async () => {
    const recordImpressions = vi.fn(async () => {});
    const res = await getFeed(
      makeDeps({
        loadVideoIdsWithAllTags: async () => [],
        recordImpressions,
        recsysFeed: async () => ({
          picks: [],
          reason: "pool_empty",
          taste: { x: 0.1, y: 0.2, shares: [{ clusterId: 1, pct: 100 }] },
        }),
      }),
      "u1",
      1,
      true,
      ["dataset:rental"],
    );
    expect(res.items).toEqual([]);
    expect(res.reason).toBe("pool_empty");
    expect(res.taste.shares[0]).toMatchObject({ clusterId: 1, pct: 100 });
    expect(res.map).toBeDefined();
    expect(recordImpressions).not.toHaveBeenCalled();
  });

  it("絞り込み中の seenReset は、候補の範囲だけを消すよう recordImpressions に伝える", async () => {
    const recordImpressions = vi.fn(async () => {});
    await getFeed(
      makeDeps({
        recordImpressions,
        recsysFeed: async () => ({
          picks: [{ videoId: "b", reason: "near" }],
          seenReset: true,
          taste: { x: 0, y: 0, shares: [] },
        }),
      }),
      "u1",
      1,
      false,
      ["dataset:rental"],
    );
    expect(recordImpressions).toHaveBeenCalledWith(
      "u1",
      [{ videoId: "b", reason: "near" }],
      true,
      ["b", "c"],
    );
  });
});

describe("getFeed", () => {
  it("§6.1 の形で返し、recsys に履歴を渡す", async () => {
    const recsysFeed = vi.fn(makeDeps().recsysFeed);
    const res = await getFeed(makeDeps({ recsysFeed }), "u1", 2, false);
    expect(recsysFeed).toHaveBeenCalledWith({
      events: [{ type: "view", videoId: "a", ratio: 1 }],
      seenIds: ["a"],
      recentDatasets: ["d1"],
      count: 2,
    });
    expect(res.items.map((i) => [i.videoId, i.reason, i.reasonLabel])).toEqual([
      ["b", "near", "好みに近い"],
      ["c", "adventure", "冒険枠"],
    ]);
    expect(res.items[0].csvRow).toEqual([["列", "値"]]);
    expect(res.items[0].sourceRef).toBe("行 #1");
    expect(res.taste.shares[0].name).toBe("ドローン");
    expect(res.taste.eventCount).toBe(1);
    expect(res).not.toHaveProperty("map");
  });

  it("配信するものに numbers と decisions を含めない", async () => {
    const res = await getFeed(makeDeps(), "u1", 2, true);
    const text = JSON.stringify(res);
    expect(text).not.toContain("numbers");
    expect(text).not.toContain("secret");
    expect(text).not.toContain("decisions");
  });

  it("includeMap のときだけ map を付ける", async () => {
    const loadMapPoints = vi.fn(makeDeps().loadMapPoints);
    const off = await getFeed(makeDeps({ loadMapPoints }), "u1", 1, false);
    expect(off.map).toBeUndefined();
    expect(loadMapPoints).not.toHaveBeenCalled();
    const on = await getFeed(makeDeps({ loadMapPoints }), "u1", 1, true);
    expect(on.map?.points).toHaveLength(1);
    expect(on.map?.clusters).toEqual([
      { id: 1, name: "ドローン", color: "#FF0000", cx: 0.1, cy: 0.2 },
    ]);
  });

  it("配信した動画を impressions に記録する(seenReset が無ければ reset=false)", async () => {
    const recordImpressions = vi.fn<FeedDeps["recordImpressions"]>(
      async () => {},
    );
    await getFeed(makeDeps({ recordImpressions }), "u1", 2, false);
    expect(recordImpressions).toHaveBeenCalledWith(
      "u1",
      [
        { videoId: "b", reason: "near" },
        { videoId: "c", reason: "adventure" },
      ],
      false,
    );
  });

  it("seenReset: true なら reset=true で記録する", async () => {
    const recordImpressions = vi.fn<FeedDeps["recordImpressions"]>(
      async () => {},
    );
    const base = makeDeps();
    await getFeed(
      makeDeps({
        recordImpressions,
        recsysFeed: async (r) => ({
          ...(await base.recsysFeed(r)),
          seenReset: true,
        }),
      }),
      "u1",
      1,
      false,
    );
    expect(recordImpressions.mock.calls[0][2]).toBe(true);
  });

  it("DB にない動画は配信も記録もしない。全部ないなら 503", async () => {
    const recordImpressions = vi.fn<FeedDeps["recordImpressions"]>(
      async () => {},
    );
    const res = await getFeed(
      makeDeps({
        recordImpressions,
        loadVideos: async () => new Map([["c", video("c")]]),
      }),
      "u1",
      2,
      false,
    );
    expect(res.items.map((i) => i.videoId)).toEqual(["c"]);
    expect(recordImpressions.mock.calls[0][1]).toEqual([
      { videoId: "c", reason: "adventure" },
    ]);

    await expect(
      getFeed(makeDeps({ loadVideos: async () => new Map() }), "u1", 1, false),
    ).rejects.toMatchObject({ status: 503 } satisfies Partial<HttpError>);
  });
});
