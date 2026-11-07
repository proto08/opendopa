import { describe, expect, it } from "vitest";
import { ANON_COOKIE, resolveAnonId } from "./anon";

const ID = "3b0f6a52-1c1e-4d0e-9a55-0f2f4c1b7e11";
const req = (
  headers: Record<string, string> = {},
  url = "http://x.test/api/feed",
) => new Request(url, { headers });

describe("resolveAnonId", () => {
  it("Cookie がなければ発行して Set-Cookie を返す", () => {
    const r = resolveAnonId(req());
    expect(r.anonId).toMatch(/^[0-9a-f-]{36}$/);
    expect(r.setCookie).toContain(`${ANON_COOKIE}=${r.anonId}`);
    expect(r.setCookie).toContain("HttpOnly");
    expect(r.setCookie).toContain("SameSite=Lax");
    expect(r.setCookie).toContain("Max-Age=31536000");
  });

  it("あれば再利用し、Set-Cookie は返さない", () => {
    const r = resolveAnonId(req({ cookie: `a=b; ${ANON_COOKIE}=${ID}` }));
    expect(r).toEqual({ anonId: ID });
  });

  it("壊れた値は再発行する", () => {
    const r = resolveAnonId(req({ cookie: `${ANON_COOKIE}=not-a-uuid` }));
    expect(r.anonId).not.toBe("not-a-uuid");
    expect(r.setCookie).toBeDefined();
  });

  it("ヘッダー・クエリで送られた別の値は使わない", () => {
    const other = "11111111-2222-4333-8444-555555555555";
    const r = resolveAnonId(
      req(
        { "x-anon-id": other, [ANON_COOKIE]: other },
        `http://x.test/api/feed?${ANON_COOKIE}=${other}&anonId=${other}`,
      ),
    );
    expect(r.anonId).not.toBe(other);
  });

  it("本番では Secure を付ける", async () => {
    const { buildSetCookie } = await import("./anon");
    expect(buildSetCookie(ID, true)).toContain("Secure");
    expect(buildSetCookie(ID, false)).not.toContain("Secure");
  });
});
