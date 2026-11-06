import { connection } from "next/server";
import { dummyFeed, parseCount } from "@/lib/feedDummy";

// GET /api/feed?count=1: ダミー版(#45)。好みを使わず、ランダムに返す。本物は #47 で置き換える。
export async function GET(request: Request) {
  await connection();
  const count = parseCount(new URL(request.url).searchParams.get("count"));
  const items = await dummyFeed(count);
  return Response.json({ items }, { headers: { "Cache-Control": "no-store" } });
}
