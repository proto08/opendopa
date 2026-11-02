import { connection } from "next/server";
import { pingDb } from "@/lib/db";

// GET /api/health: DB に接続できれば 200、できなければ 503(ADR-0012 A10)。
export async function GET() {
  // ビルド時に事前生成させず、リクエストのたびに実行する
  await connection();

  const headers = { "Cache-Control": "no-store" };
  if (await pingDb()) {
    return Response.json({ status: "ok", db: "ok" }, { headers });
  }
  return Response.json({ error: "database unreachable" }, { status: 503, headers });
}
