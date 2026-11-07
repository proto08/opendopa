import { beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { ANON_COOKIE } from "./anon";
import { apiHandler, HttpError, json, parseJsonBody, parseQuery } from "./http";
import { RecsysError } from "./recsys-client";

const ID = "3b0f6a52-1c1e-4d0e-9a55-0f2f4c1b7e11";
const call = (
  h: (r: Request) => Promise<Response>,
  cookie = `${ANON_COOKIE}=${ID}`,
) =>
  h(new Request("http://x.test/api/t", { headers: cookie ? { cookie } : {} }));

describe("apiHandler", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("すべてのレスポンスに no-store が付く(ハンドラが付け忘れても)", async () => {
    const h = apiHandler(() => new Response("ok"));
    expect((await call(h)).headers.get("Cache-Control")).toBe("no-store");
  });

  it("匿名 ID がなければ Cookie を発行し、ハンドラへ渡す", async () => {
    let seen = "";
    const h = apiHandler(({ anonId }) => {
      seen = anonId;
      return json({ ok: true });
    });
    const res = await call(h, "");
    expect(res.headers.get("Set-Cookie")).toContain(`${ANON_COOKIE}=${seen}`);
  });

  it("エラーは { error } と適切なステータス", async () => {
    const res = await call(
      apiHandler(() => {
        throw new HttpError(404, "no such video");
      }),
    );
    expect(res.status).toBe(404);
    expect(await res.json()).toEqual({ error: "no such video" });
    expect(res.headers.get("Cache-Control")).toBe("no-store");
  });

  it("RecsysError は 502、想定外の例外は 500", async () => {
    const r502 = await call(
      apiHandler(() => Promise.reject(new RecsysError("down"))),
    );
    expect(r502.status).toBe(502);
    const r500 = await call(
      apiHandler(() => Promise.reject(new Error("boom"))),
    );
    expect(r500.status).toBe(500);
    expect(await r500.json()).toEqual({ error: "internal server error" });
  });

  it("1 秒に 11 回目は 429(no-store つき)", async () => {
    const id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
    const h = apiHandler(() => json({ ok: true }));
    const statuses: number[] = [];
    let last!: Response;
    for (let i = 0; i < 11; i++) {
      last = await call(h, `${ANON_COOKIE}=${id}`);
      statuses.push(last.status);
    }
    expect(statuses.slice(0, 10).every((s) => s === 200)).toBe(true);
    expect(statuses[10]).toBe(429);
    expect(last.headers.get("Cache-Control")).toBe("no-store");
    expect(await last.json()).toEqual({ error: "too many requests" });
  });
});

describe("入力の検証", () => {
  const schema = z.object({ n: z.coerce.number().int().min(1).max(3) });

  it("本文が不正なら 400", async () => {
    const bad = new Request("http://x.test", { method: "POST", body: "{" });
    await expect(parseJsonBody(bad, schema)).rejects.toMatchObject({
      status: 400,
    });
    const ng = new Request("http://x.test", {
      method: "POST",
      body: JSON.stringify({ n: 9 }),
    });
    await expect(parseJsonBody(ng, schema)).rejects.toMatchObject({
      status: 400,
    });
  });

  it("クエリを検証する", () => {
    expect(parseQuery(new Request("http://x.test/?n=2"), schema)).toEqual({
      n: 2,
    });
    expect(() => parseQuery(new Request("http://x.test/?n=0"), schema)).toThrow(
      HttpError,
    );
  });
});
