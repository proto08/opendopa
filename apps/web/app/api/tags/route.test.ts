import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/server", () => ({ connection: vi.fn(async () => {}) }));

const deps = vi.hoisted(() => ({ current: undefined as unknown }));
vi.mock("@/lib/tags", async (orig) => ({
  ...(await orig<typeof import("@/lib/tags")>()),
  defaultTagsDeps: () => deps.current,
}));

import { GET } from "@/app/api/tags/route";
import { ANON_COOKIE } from "@/lib/anon";

const ID = "3b0f6a52-1c1e-4d0e-9a55-0f2f4c1b7e11";
const tag = {
  id: "region:hokkaido",
  kind: "region",
  label: "北海道",
  yomi: "ほっかいどう",
  count: 42,
};

const get = () =>
  GET(
    new Request("http://x.test/api/tags", {
      headers: { cookie: `${ANON_COOKIE}=${ID}` },
    }),
  );

describe("GET /api/tags", () => {
  beforeEach(() => {
    deps.current = { loadTags: async () => [tag] };
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("全タグと件数を返し、no-store", async () => {
    const res = await get();
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
    expect(await res.json()).toEqual({ tags: [tag] });
  });

  it("DB が失敗したら 500", async () => {
    deps.current = {
      loadTags: async () => {
        throw new Error("db down");
      },
    };
    expect((await get()).status).toBe(500);
  });
});
