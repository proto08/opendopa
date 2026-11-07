import { describe, expect, it, vi } from "vitest";
import { feedQuery, getFeed, type FeedDeps } from "./feed";
import { HttpError } from "./http";
import type { VideoRow } from "./queries/videos";

const scene = (id: string) => ({ videoId: id, headline: `h-${id}`, numbers: [{ secret: 1 }] });
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
    loadClusters: async () => [{ id: 1, name: "ドローン", color: "#FF0000", cx: 0.1, cy: 0.2 }],
    loadMapPoints: async () => [{ videoId: "b", datasetId: "d1", x: 0.1, y: 0.2, clusterId: 1 }],
    loadViewLog: async () => [],
    countViews: async () => 1,
    ...over,
  };
}

describe("feedQuery", () => {
  const parse = (q: Record<string, string>) => feedQuery.safeParse(q);
  it("既定は count=1、includeMap=0", () => {
    expect(parse({})).toMatchObject({ success: true, data: { count: 1, includeMap: "0" } });
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
    const recordImpressions = vi.fn<FeedDeps["recordImpressions"]>(async () => {});
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
    const recordImpressions = vi.fn<FeedDeps["recordImpressions"]>(async () => {});
    const base = makeDeps();
    await getFeed(
      makeDeps({
        recordImpressions,
        recsysFeed: async (r) => ({ ...(await base.recsysFeed(r)), seenReset: true }),
      }),
      "u1",
      1,
      false,
    );
    expect(recordImpressions.mock.calls[0][2]).toBe(true);
  });

  it("DB にない動画は配信も記録もしない。全部ないなら 503", async () => {
    const recordImpressions = vi.fn<FeedDeps["recordImpressions"]>(async () => {});
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
    expect(recordImpressions.mock.calls[0][1]).toEqual([{ videoId: "c", reason: "adventure" }]);

    await expect(
      getFeed(makeDeps({ loadVideos: async () => new Map() }), "u1", 1, false),
    ).rejects.toMatchObject({ status: 503 } satisfies Partial<HttpError>);
  });
});
