import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { pingRecsys } from "./recsys-client";

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
    const [url, init] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    expect(url.href).toBe("http://recsys.test:8080/internal/ping");
    expect(init.headers).toEqual({ "X-Internal-Token": "tok" });
  });

  it("401 や接続失敗は false", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 401 })));
    expect(await pingRecsys()).toBe(false);
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new Error("refused"))));
    expect(await pingRecsys()).toBe(false);
  });

  it("環境変数がなければ false", async () => {
    vi.stubEnv("INTERNAL_TOKEN", "");
    expect(await pingRecsys()).toBe(false);
  });
});
