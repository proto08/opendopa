import { connection } from "next/server";
import { pingRecsys } from "@/lib/recsys-client";

// GET /api/health/recsys: web → recsys の内部 HTTP(X-Internal-Token)がつながれば 200、
// つながらなければ 503。開発時の疎通確認用(ADR-0013 A4)。
export async function GET() {
  await connection();

  const headers = { "Cache-Control": "no-store" };
  if (await pingRecsys()) {
    return Response.json({ status: "ok", recsys: "ok" }, { headers });
  }
  return Response.json(
    { error: "recsys unreachable" },
    { status: 503, headers },
  );
}
