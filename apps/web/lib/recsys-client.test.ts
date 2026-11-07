import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  pingRecsys,
  RecsysError,
  recsysFeed,
  recsysTaste,
} from "./recsys-client";

describe("pingRecsys", () => {
  beforeEach(() => {
    vi.stubEnv("RECSYS_URL", "http://recsys.test:8080");
    vi.stubEnv("INTERNAL_TOKEN", "tok");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("X-Internal-Token を付けて /internal/ping を呼ぶ", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await pingRecsys()).toBe(true);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      URL,
      RequestInit,
    ];
    expect(url.href).toBe("http://recsys.test:8080/internal/ping");
    expect(init.headers).toEqual({ "X-Internal-Token": "tok" });
  });

  it("401 や接続失敗は false", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("", { status: 401 })),
    );
    expect(await pingRecsys()).toBe(false);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Promise.reject(new Error("refused"))),
    );
    expect(await pingRecsys()).toBe(false);
  });

  it("環境変数がなければ false", async () => {
    vi.stubEnv("INTERNAL_TOKEN", "");
    expect(await pingRecsys()).toBe(false);
  });
});

describe("recsysFeed / recsysTaste", () => {
  const taste = { x: 0.1, y: 0.2, shares: [{ clusterId: 1, pct: 100 }] };
  beforeEach(() => {
    vi.stubEnv("RECSYS_URL", "http://recsys.test:8080");
    vi.stubEnv("INTERNAL_TOKEN", "tok");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("feed: トークンつきで POST し、本文を送って結果を返す", async () => {
    const res = { picks: [{ videoId: "a-1", reason: "first" }], taste };
    const fetchMock = vi.fn(async () => Response.json(res));
    vi.stubGlobal("fetch", fetchMock);
    const req = { events: [], seenIds: [], recentDatasets: [], count: 2 };
    expect(await recsysFeed(req)).toEqual(res);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      URL,
      RequestInit,
    ];
    expect(url.href).toBe("http://recsys.test:8080/internal/feed");
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({
      "X-Internal-Token": "tok",
      "Content-Type": "application/json",
    });
    expect(JSON.parse(init.body as string)).toEqual(req);
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it("taste: /internal/taste を呼ぶ", async () => {
    const fetchMock = vi.fn(async () => Response.json({ taste }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await recsysTaste({ events: [] })).toEqual({ taste });
    const [url] = fetchMock.mock.calls[0] as unknown as [URL];
    expect(url.pathname).toBe("/internal/taste");
  });

  it("5xx・接続失敗・タイムアウト・壊れた本文は RecsysError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("", { status: 503 })),
    );
    await expect(recsysTaste({ events: [] })).rejects.toBeInstanceOf(
      RecsysError,
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Promise.reject(new DOMException("timeout", "TimeoutError")),
      ),
    );
    await expect(recsysTaste({ events: [] })).rejects.toBeInstanceOf(
      RecsysError,
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("not json", { status: 200 })),
    );
    await expect(
      recsysFeed({ events: [], seenIds: [], recentDatasets: [], count: 1 }),
    ).rejects.toBeInstanceOf(RecsysError);
  });
});
