// recsys(Rust)への内部 HTTP(設計書 §6.6)。URL とトークンは環境変数 RECSYS_URL、INTERNAL_TOKEN から取る。

import { recsysAttributes, startRecsysCall } from "./telemetry";
import type {
  RecsysFeedRequest,
  RecsysFeedResponse,
  RecsysTasteRequest,
  RecsysTasteResponse,
} from "./types";

const TIMEOUT_MS = 2000;

/** recsys の呼び出しに失敗した(接続不可・タイムアウト・5xx・想定外の本文)。呼び出し側は 502 を返す。 */
export class RecsysError extends Error {
  constructor(
    message: string,
    /** recsys が返した HTTP ステータス(接続できなかったときは無い) */
    readonly status?: number,
  ) {
    super(message);
    this.name = "RecsysError";
  }
}

function config(): { url: string; token: string } {
  const url = process.env.RECSYS_URL;
  const token = process.env.INTERNAL_TOKEN;
  if (!url || !token) {
    throw new Error("RECSYS_URL and INTERNAL_TOKEN must be set");
  }
  return { url, token };
}

/** recsys に認証つきで GET する。 */
export async function recsysGet(path: string): Promise<Response> {
  const { url, token } = config();
  return fetch(new URL(path, url), {
    headers: { "X-Internal-Token": token },
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
}

/** recsys に認証つきで JSON を POST し、JSON を返す。失敗は `RecsysError`。 */
async function recsysPost<T>(path: string, body: unknown): Promise<T> {
  const call = startRecsysCall(path);
  try {
    const out = await recsysPostInner<T>(path, body);
    call.end(recsysAttributes(path, true));
    return out;
  } catch (e) {
    call.end(
      recsysAttributes(
        path,
        false,
        e instanceof RecsysError ? e.status : undefined,
      ),
      e,
    );
    throw e;
  }
}

async function recsysPostInner<T>(path: string, body: unknown): Promise<T> {
  const { url, token } = config();
  let res: Response;
  try {
    res = await fetch(new URL(path, url), {
      method: "POST",
      headers: {
        "X-Internal-Token": token,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (e) {
    throw new RecsysError(`recsys ${path}: request failed: ${String(e)}`);
  }
  if (!res.ok)
    throw new RecsysError(`recsys ${path}: status ${res.status}`, res.status);
  try {
    return (await res.json()) as T;
  } catch {
    throw new RecsysError(`recsys ${path}: invalid JSON response`);
  }
}

/** `POST /internal/feed`: 次の動画と `taste` を得る。 */
export function recsysFeed(
  req: RecsysFeedRequest,
): Promise<RecsysFeedResponse> {
  return recsysPost("/internal/feed", req);
}

/** `POST /internal/taste`: `taste` だけを得る。 */
export function recsysTaste(
  req: RecsysTasteRequest,
): Promise<RecsysTasteResponse> {
  return recsysPost("/internal/taste", req);
}

/** recsys に認証つきでつながるか(`GET /internal/ping` が 200 か)を確かめる。 */
export async function pingRecsys(): Promise<boolean> {
  try {
    return (await recsysGet("/internal/ping")).ok;
  } catch {
    return false;
  }
}
