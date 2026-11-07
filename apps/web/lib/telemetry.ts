// 監視(Application Insights)に送るイベントの作り方(イシュー #61、docs/adr/0061-application-insights.md)。
// 送信の有効・無効は instrumentation.ts が決める。ここは @opentelemetry/api だけを使うので、SDK が登録されていなければ
// 何も起きない(ローカル・テスト)。送る属性は下の関数が作る固定の項目だけ。匿名 ID の生の値と csvRow は渡さない。
import { metrics, SpanStatusCode, trace } from "@opentelemetry/api";

const NAME = "opendopa-web";

/** 接続文字列が設定されているときだけ計測する(ローカル・テストでは false) */
export function telemetryEnabled(
  env: Record<string, string | undefined> = process.env,
): boolean {
  return !!env.APPLICATIONINSIGHTS_CONNECTION_STRING?.trim();
}

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

/** エラー文に匿名 ID(UUID)が紛れても送らないよう、伏せる */
export function redact(text: string): string {
  return text.replace(UUID, "[id]").slice(0, 500);
}

export type Attrs = Record<string, string | number | boolean>;

/** `/api/*` のリクエストの属性。パスはクエリ文字列を除く(匿名 ID は Cookie にあり、ここには出ない) */
export function apiAttributes(
  method: string,
  url: string,
  status: number,
): Attrs {
  return {
    "http.request.method": method,
    "url.path": new URL(url).pathname,
    "http.response.status_code": status,
  };
}

/** recsys 呼び出しの属性。`path` は `/internal/feed` など固定のパス */
export function recsysAttributes(
  path: string,
  ok: boolean,
  status?: number,
): Attrs {
  const a: Attrs = { "recsys.path": path, "recsys.ok": ok };
  if (status !== undefined) a["http.response.status_code"] = status;
  return a;
}

function errorText(e: unknown): string {
  return redact(e instanceof Error ? `${e.name}: ${e.message}` : String(e));
}

interface Handle {
  /** 終了を記録する。`error` は失敗したときの原因 */
  end(attrs: Attrs, error?: unknown): void;
}

function start(
  span: string,
  histogram: string,
  description: string,
  base: Attrs,
): Handle {
  const t0 = performance.now();
  const s = trace.getTracer(NAME).startSpan(span, { attributes: base });
  return {
    end(attrs, error) {
      const ms = performance.now() - t0;
      const all = { ...base, ...attrs };
      s.setAttributes(attrs);
      if (error !== undefined) {
        s.setStatus({ code: SpanStatusCode.ERROR, message: errorText(error) });
        all["error.type"] = error instanceof Error ? error.name : "unknown";
      }
      s.end();
      metrics
        .getMeter(NAME)
        .createHistogram(histogram, { description, unit: "ms" })
        .record(ms, all);
    },
  };
}

/** `/api/*` のリクエスト1件の計測を始める(応答時間は開始から `end` まで) */
export function startApiRequest(method: string, url: string): Handle {
  return start("api.request", "opendopa.api.duration", "API の応答時間", {
    "http.request.method": method,
    "url.path": new URL(url).pathname,
  });
}

/** recsys への内部 HTTP 1回の計測を始める */
export function startRecsysCall(path: string): Handle {
  return start(
    "recsys.call",
    "opendopa.recsys.duration",
    "recsys 呼び出しの時間",
    { "recsys.path": path },
  );
}
