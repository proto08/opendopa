import type { ZodError, ZodType } from "zod";
import { resolveAnonId } from "./anon";
import { rateLimiter } from "./rate-limit";
import { RecsysError } from "./recsys-client";

// /api/* の共通ヘルパー(設計書 §6.5)。新しい API は `apiHandler` で包むだけで、
// 匿名 ID の Cookie、`Cache-Control: no-store`、レート制限、エラー形式 `{ "error": "message" }` を満たす。

/** ハンドラから投げると、その HTTP ステータスと `{ error }` で返る。 */
export class HttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export interface ApiContext {
  anonId: string;
  req: Request;
}

/** `Cache-Control: no-store` を付けた JSON レスポンス。 */
export function json(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Cache-Control", "no-store");
  return Response.json(body, { ...init, headers });
}

export function errorResponse(
  status: number,
  message: string,
  init: ResponseInit = {},
): Response {
  return json({ error: message }, { ...init, status });
}

/** 本文の JSON を zod で検証する。外れたら 400。 */
export async function parseJsonBody<T>(
  req: Request,
  schema: ZodType<T>,
): Promise<T> {
  let raw: unknown;
  try {
    raw = await req.json();
  } catch {
    throw new HttpError(400, "invalid JSON body");
  }
  return validate(schema, raw);
}

/** クエリ文字列を zod で検証する。外れたら 400。同じキーが複数あれば、その値は配列になる。 */
export function parseQuery<T>(req: Request, schema: ZodType<T>): T {
  const raw: Record<string, string | string[]> = {};
  for (const [k, v] of new URL(req.url).searchParams) {
    const prev = raw[k];
    if (prev === undefined) raw[k] = v;
    else raw[k] = Array.isArray(prev) ? [...prev, v] : [prev, v];
  }
  return validate(schema, raw);
}

function validate<T>(schema: ZodType<T>, raw: unknown): T {
  const r = schema.safeParse(raw);
  if (!r.success) throw new HttpError(400, describe(r.error));
  return r.data;
}

function describe(e: ZodError): string {
  return e.issues
    .map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`)
    .join("; ");
}

function toErrorResponse(e: unknown): Response {
  if (e instanceof HttpError) return errorResponse(e.status, e.message);
  if (e instanceof RecsysError)
    return errorResponse(502, "recommendation service unavailable");
  console.error(e);
  return errorResponse(500, "internal server error");
}

/** Route Handler を包む。匿名 ID の確認・発行、レート制限、エラー変換、`no-store` を行う。 */
export function apiHandler(
  handler: (ctx: ApiContext) => Promise<Response> | Response,
) {
  return async (req: Request): Promise<Response> => {
    const { anonId, setCookie } = resolveAnonId(req);
    let res: Response;
    if (!rateLimiter.allow(anonId)) {
      res = errorResponse(429, "too many requests", {
        headers: { "Retry-After": "1" },
      });
    } else {
      try {
        res = await handler({ anonId, req });
      } catch (e) {
        res = toErrorResponse(e);
      }
    }
    // ハンドラが返したレスポンスにも必ず付ける
    const headers = new Headers(res.headers);
    headers.set("Cache-Control", "no-store");
    if (setCookie) headers.append("Set-Cookie", setCookie);
    return new Response(res.body, {
      status: res.status,
      statusText: res.statusText,
      headers,
    });
  };
}
