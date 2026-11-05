import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/server", () => ({ connection: vi.fn(async () => {}) }));
vi.mock("@/lib/recsys-client", () => ({ pingRecsys: vi.fn() }));

import { pingRecsys } from "@/lib/recsys-client";
import { GET } from "./route";

describe("GET /api/health/recsys", () => {
  beforeEach(() => vi.mocked(pingRecsys).mockReset());

  it("recsys につながれば 200", async () => {
    vi.mocked(pingRecsys).mockResolvedValue(true);
    const res = await GET();
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: "ok", recsys: "ok" });
  });

  it("つながらなければ 503", async () => {
    vi.mocked(pingRecsys).mockResolvedValue(false);
    const res = await GET();
    expect(res.status).toBe(503);
    expect(await res.json()).toEqual({ error: "recsys unreachable" });
  });
});
