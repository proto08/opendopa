import { beforeEach, describe, expect, it, vi } from "vitest";

// 記録されたものを集める。SDK が無くても、API を呼んだ内容でイベントに何が入るかを確かめる
const recorded = vi.hoisted(() => ({ items: [] as unknown[] }));
vi.mock("@opentelemetry/api", () => {
  const span = {
    setAttributes: (a: unknown) => recorded.items.push(a),
    setStatus: (s: unknown) => recorded.items.push(s),
    end: () => {},
  };
  return {
    SpanStatusCode: { ERROR: 2 },
    trace: {
      getTracer: () => ({
        startSpan: (name: string, o: { attributes: unknown }) => {
          recorded.items.push(name, o.attributes);
          return span;
        },
      }),
    },
    metrics: {
      getMeter: () => ({
        createHistogram: () => ({
          record: (v: number, a: unknown) => recorded.items.push(v, a),
        }),
      }),
    },
  };
});

import { ANON_COOKIE } from "@/lib/anon";
import { apiHandler, HttpError, json } from "@/lib/http";
import { RecsysError } from "@/lib/recsys-client";
import {
  apiAttributes,
  recsysAttributes,
  redact,
  telemetryEnabled,
} from "@/lib/telemetry";

const ID = "3b0f6a52-1c1e-4d0e-9a55-0f2f4c1b7e11";

beforeEach(() => {
  recorded.items.length = 0;
});

describe("telemetryEnabled", () => {
  it("接続文字列がなければ無効", () => {
    expect(telemetryEnabled({})).toBe(false);
    expect(
      telemetryEnabled({ APPLICATIONINSIGHTS_CONNECTION_STRING: " " }),
    ).toBe(false);
  });
  it("接続文字列があれば有効", () => {
    expect(
      telemetryEnabled({
        APPLICATIONINSIGHTS_CONNECTION_STRING: "InstrumentationKey=x",
      }),
    ).toBe(true);
  });
});

describe("属性", () => {
  it("API の属性はパスだけで、クエリ文字列を含まない", () => {
    const a = apiAttributes("GET", `http://x/api/feed?count=1&q=${ID}`, 200);
    expect(a).toEqual({
      "http.request.method": "GET",
      "url.path": "/api/feed",
      "http.response.status_code": 200,
    });
  });
  it("recsys の属性", () => {
    expect(recsysAttributes("/internal/feed", false, 503)).toEqual({
      "recsys.path": "/internal/feed",
      "recsys.ok": false,
      "http.response.status_code": 503,
    });
  });
  it("エラー文の UUID を伏せる", () => {
    expect(redact(`failed for ${ID}`)).toBe("failed for [id]");
  });
});

describe("apiHandler の計測に匿名 ID の生の値が含まれない", () => {
  function req(path: string) {
    return new Request(`http://localhost${path}`, {
      headers: { cookie: `${ANON_COOKIE}=${ID}` },
    });
  }

  it("成功", async () => {
    const res = await apiHandler(() => json({ ok: true }))(req("/api/x?a=1"));
    expect(res.status).toBe(200);
    const text = JSON.stringify(recorded.items);
    expect(text).toContain("/api/x");
    expect(text).not.toContain(ID);
  });

  it("失敗(原因に匿名 ID が入っていても伏せる)", async () => {
    const handler = apiHandler(() => {
      throw new RecsysError(`bad for ${ID}`, 503);
    });
    const res = await handler(req("/api/feed"));
    expect(res.status).toBe(502);
    const text = JSON.stringify(recorded.items);
    expect(text).toContain("RecsysError");
    expect(text).not.toContain(ID);
  });

  it("HttpError は失敗として記録しない", async () => {
    const res = await apiHandler(() => {
      throw new HttpError(400, "bad");
    })(req("/api/feed"));
    expect(res.status).toBe(400);
    expect(JSON.stringify(recorded.items)).not.toContain("error.type");
  });
});
