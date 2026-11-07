import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/server", () => ({ connection: vi.fn(async () => {}) }));

const deps = vi.hoisted(() => ({ current: undefined as unknown }));
vi.mock("@/lib/feed", async (orig) => ({
  ...(await orig<typeof import("@/lib/feed")>()),
  defaultDeps: () => deps.current,
}));

import { GET } from "@/app/api/feed/route";
import { ANON_COOKIE } from "@/lib/anon";
import { RecsysError } from "@/lib/recsys-client";

const ID = "3b0f6a52-1c1e-4d0e-9a55-0f2f4c1b7e11";

function fakeDeps(over: Record<string, unknown> = {}) {
  return {
    loadEvents: async () => [],
    loadImpressions: async () => ({ seenIds: [], recentDatasets: [] }),
    recsysFeed: async () => ({
      picks: [{ videoId: "v1", reason: "first" }],
      taste: { x: 0.5, y: 0.5, shares: [] },
    }),
    loadVideos: async () =>
      new Map([
        [
          "v1",
          {
            id: "v1",
            headline: "h",
            scene: { videoId: "v1" },
            csvRow: [],
            sourceRef: "r",
          },
        ],
      ]),
    recordImpressions: vi.fn(async () => {}),
    loadClusters: async () => [],
    loadMapPoints: async () => [],
    loadViewLog: async () => [],
    countViews: async () => 0,
    ...over,
  };
}

const get = (qs = "", cookie = true) =>
  GET(
    new Request(`http://x.test/api/feed${qs}`, {
      headers: cookie ? { cookie: `${ANON_COOKIE}=${ID}` } : {},
    }),
  );

describe("GET /api/feed", () => {
  beforeEach(() => {
    deps.current = fakeDeps();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("成功時は items と taste を返し、no-store", async () => {
    const res = await get("?count=1");
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
    const body = await res.json();
    expect(body.items[0]).toMatchObject({
      videoId: "v1",
      reason: "first",
      reasonLabel: "最初の1本",
    });
    expect(body.taste.summary).toBe("まだ見ていないので、好みはわかりません");
    expect(body.map).toBeUndefined();
  });

  it("count=0 / 4 は 400", async () => {
    for (const c of ["0", "4"]) {
      const res = await get(`?count=${c}`);
      expect(res.status).toBe(400);
      expect(await res.json()).toHaveProperty("error");
    }
  });

  it("includeMap=1 のときだけ map が付く", async () => {
    expect((await (await get("?includeMap=1")).json()).map).toEqual({
      points: [],
      clusters: [],
    });
    expect((await (await get("?includeMap=0")).json()).map).toBeUndefined();
  });

  it("初回(Cookie なし)は Cookie を発行し、その匿名 ID で記録する", async () => {
    const d = fakeDeps();
    deps.current = d;
    const res = await get("", false);
    const setCookie = res.headers.get("Set-Cookie") ?? "";
    expect(setCookie).toContain(`${ANON_COOKIE}=`);
    const issued = /od_aid=([^;]+)/.exec(setCookie)![1];
    expect(d.recordImpressions).toHaveBeenCalledWith(
      issued,
      [{ videoId: "v1", reason: "first" }],
      false,
    );
  });

  it("recsys が落ちている・遅いときは 502", async () => {
    deps.current = fakeDeps({
      recsysFeed: async () => {
        throw new RecsysError("timeout");
      },
    });
    const res = await get();
    expect(res.status).toBe(502);
    expect(await res.json()).toEqual({
      error: "recommendation service unavailable",
    });
  });
});
