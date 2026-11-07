import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/server", () => ({ connection: vi.fn(async () => {}) }));

const deps = vi.hoisted(() => ({ current: undefined as unknown }));
vi.mock("@/lib/interact", async (orig) => ({
  ...(await orig<typeof import("@/lib/interact")>()),
  defaultInteractDeps: () => deps.current,
}));

import { POST as postLikeRoute } from "@/app/api/like/route";
import { POST as postViewRoute } from "@/app/api/view/route";
import { ANON_COOKIE } from "@/lib/anon";
import { RecsysError } from "@/lib/recsys-client";

// レート制限(匿名 ID ごと 10 回/秒)に当たらないよう、リクエストごとに別の匿名 ID を使う
let seq = 0;
let ID = "";
function nextId(): string {
  return `3b0f6a52-1c1e-4d0e-9a55-${String(++seq).padStart(12, "0")}`;
}
const VIEW_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7";

function fakeDeps(over: Record<string, unknown> = {}) {
  return {
    loadDuration: async (id: string) => (id === "v1" ? 20 : null),
    insertView: vi.fn(async () => true),
    insertLike: vi.fn(async () => true),
    loadVideoLogInfo: async () => ({ headline: "見出し", reason: "near", liked: true }),
    loadEvents: async () => [],
    recsysTaste: vi.fn(async () => ({ taste: { x: 0.5, y: 0.5, shares: [] } })),
    loadClusters: async () => [],
    countViews: async () => 1,
    loadViewLog: async () => [],
    ...over,
  };
}

const post = (
  route: typeof postViewRoute,
  body: unknown,
  contentType = "application/json",
) => {
  ID = nextId();
  return route(
    new Request("http://x.test/api/x", {
      method: "POST",
      headers: { cookie: `${ANON_COOKIE}=${ID}`, "content-type": contentType },
      body: typeof body === "string" ? body : JSON.stringify(body),
    }),
  );
};

describe("POST /api/view", () => {
  beforeEach(() => {
    deps.current = fakeDeps();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("保存して taste と logEntry を返す。ratio は 1 で頭打ち", async () => {
    const d = fakeDeps();
    deps.current = d;
    const res = await post(postViewRoute, { viewId: VIEW_ID, videoId: "v1", watchedSec: 50 });
    expect(res.status).toBe(200);
    expect(d.insertView).toHaveBeenCalledWith({
      viewId: VIEW_ID,
      anonId: ID,
      videoId: "v1",
      watchedSec: 50,
      ratio: 1,
    });
    const body = await res.json();
    expect(body.taste.eventCount).toBe(1);
    expect(body.logEntry).toEqual({
      videoId: "v1",
      headline: "見出し",
      reasonLabel: "好みに近い",
      ratio: 1,
      liked: true,
    });
  });

  it("ratio = watchedSec / duration_sec", async () => {
    const d = fakeDeps();
    deps.current = d;
    await post(postViewRoute, { viewId: VIEW_ID, videoId: "v1", watchedSec: 5 });
    expect(d.insertView).toHaveBeenCalledWith(expect.objectContaining({ ratio: 0.25 }));
  });

  it("viewId の重複(保存されなかった)でも 200 で taste を返す", async () => {
    deps.current = fakeDeps({ insertView: vi.fn(async () => false) });
    const res = await post(postViewRoute, { viewId: VIEW_ID, videoId: "v1", watchedSec: 5 });
    expect(res.status).toBe(200);
    expect((await res.json()).taste).toBeDefined();
  });

  it("sendBeacon 相当(text/plain の JSON 本文)を受け付ける", async () => {
    const res = await post(
      postViewRoute,
      JSON.stringify({ viewId: VIEW_ID, videoId: "v1", watchedSec: 5 }),
      "text/plain;charset=UTF-8",
    );
    expect(res.status).toBe(200);
  });

  it.each([
    ["存在しない videoId", { viewId: VIEW_ID, videoId: "nope", watchedSec: 1 }],
    ["watchedSec が負", { viewId: VIEW_ID, videoId: "v1", watchedSec: -1 }],
    ["watchedSec > duration * 10", { viewId: VIEW_ID, videoId: "v1", watchedSec: 200.1 }],
    ["viewId が UUID でない", { viewId: "abc", videoId: "v1", watchedSec: 1 }],
    ["watchedSec が数値でない", { viewId: VIEW_ID, videoId: "v1", watchedSec: "1" }],
  ])("400: %s", async (_n, body) => {
    const d = fakeDeps();
    deps.current = d;
    const res = await post(postViewRoute, body);
    expect(res.status).toBe(400);
    expect(await res.json()).toHaveProperty("error");
    expect(d.insertView).not.toHaveBeenCalled();
  });

  it("本文が JSON でなければ 400", async () => {
    expect((await post(postViewRoute, "not json")).status).toBe(400);
  });

  it("duration * 10 ちょうどは受け付ける", async () => {
    const res = await post(postViewRoute, { viewId: VIEW_ID, videoId: "v1", watchedSec: 200 });
    expect(res.status).toBe(200);
  });

  it("recsys が落ちたら 502", async () => {
    deps.current = fakeDeps({
      recsysTaste: async () => {
        throw new RecsysError("down");
      },
    });
    expect((await post(postViewRoute, { viewId: VIEW_ID, videoId: "v1", watchedSec: 1 })).status).toBe(502);
  });
});

describe("POST /api/like", () => {
  beforeEach(() => {
    deps.current = fakeDeps();
  });

  it("状態を保存して taste を返す", async () => {
    const d = fakeDeps();
    deps.current = d;
    const res = await post(postLikeRoute, { videoId: "v1", liked: true });
    expect(res.status).toBe(200);
    expect(d.insertLike).toHaveBeenCalledWith({ anonId: ID, videoId: "v1", liked: true });
    expect((await res.json()).taste.eventCount).toBe(1);
  });

  it("同じ状態(追加されなかった)でも 200", async () => {
    deps.current = fakeDeps({ insertLike: vi.fn(async () => false) });
    expect((await post(postLikeRoute, { videoId: "v1", liked: false })).status).toBe(200);
  });

  it("sendBeacon 相当の text/plain を受け付ける", async () => {
    const res = await post(postLikeRoute, JSON.stringify({ videoId: "v1", liked: true }), "text/plain");
    expect(res.status).toBe(200);
  });

  it.each([
    ["存在しない videoId", { videoId: "nope", liked: true }],
    ["liked が boolean でない", { videoId: "v1", liked: "true" }],
    ["liked がない", { videoId: "v1" }],
  ])("400: %s", async (_n, body) => {
    const res = await post(postLikeRoute, body);
    expect(res.status).toBe(400);
  });
});
