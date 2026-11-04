import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/server", () => ({ connection: vi.fn(async () => {}) }));
vi.mock("@/lib/db", () => ({ pingDb: vi.fn() }));

import { pingDb } from "@/lib/db";
import { GET } from "./route";

describe("GET /api/health", () => {
  beforeEach(() => vi.mocked(pingDb).mockReset());

  it("DB に接続できれば 200", async () => {
    vi.mocked(pingDb).mockResolvedValue(true);
    const res = await GET();
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
    expect(await res.json()).toEqual({ status: "ok", db: "ok" });
  });

  it("DB に接続できなければ 503", async () => {
    vi.mocked(pingDb).mockResolvedValue(false);
    const res = await GET();
    expect(res.status).toBe(503);
    expect(await res.json()).toEqual({ error: "database unreachable" });
  });
});
