// recsys(Rust)への内部 HTTP(設計書 §6.6)。URL とトークンは環境変数 RECSYS_URL、INTERNAL_TOKEN から取る。

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
    signal: AbortSignal.timeout(2000),
  });
}

/** recsys に認証つきでつながるか(`GET /internal/ping` が 200 か)を確かめる。 */
export async function pingRecsys(): Promise<boolean> {
  try {
    return (await recsysGet("/internal/ping")).ok;
  } catch {
    return false;
  }
}
