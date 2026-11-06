import { randomUUID } from "node:crypto";

// 匿名 ID(設計書 §5)。サーバーが発行して `od_aid` Cookie に入れる。
// クライアントから受け取るのは Cookie の値だけ。ヘッダー・本文・クエリの値は匿名 ID に使わない。

export const ANON_COOKIE = "od_aid";
const MAX_AGE_SEC = 60 * 60 * 24 * 365; // 1 年
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export interface AnonResult {
  anonId: string;
  /** 発行した(または再発行した)ときだけ入る `Set-Cookie` の値。 */
  setCookie?: string;
}

function readCookie(header: string | null, name: string): string | undefined {
  if (!header) return undefined;
  for (const part of header.split(";")) {
    const eq = part.indexOf("=");
    if (eq < 0) continue;
    if (part.slice(0, eq).trim() === name) return part.slice(eq + 1).trim();
  }
  return undefined;
}

export function buildSetCookie(anonId: string, secure = process.env.NODE_ENV === "production"): string {
  const attrs = [`${ANON_COOKIE}=${anonId}`, "Path=/", `Max-Age=${MAX_AGE_SEC}`, "HttpOnly", "SameSite=Lax"];
  if (secure) attrs.push("Secure");
  return attrs.join("; ");
}

/** リクエストの Cookie から匿名 ID を取り出す。なければ・壊れていれば新しく発行する。 */
export function resolveAnonId(req: Request): AnonResult {
  const value = readCookie(req.headers.get("cookie"), ANON_COOKIE);
  if (value && UUID_RE.test(value)) return { anonId: value };
  const anonId = randomUUID();
  return { anonId, setCookie: buildSetCookie(anonId) };
}
