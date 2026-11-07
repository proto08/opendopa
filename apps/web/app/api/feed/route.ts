import { connection } from "next/server";
import { defaultDeps, feedQuery, getFeed } from "@/lib/feed";
import { apiHandler, json, parseQuery } from "@/lib/http";

// GET /api/feed?count=1&includeMap=0(設計書 §6.1)。匿名 ID の確認、レート制限、エラー変換は apiHandler。
export const GET = apiHandler(async ({ anonId, req }) => {
  await connection();
  const q = parseQuery(req, feedQuery);
  return json(
    await getFeed(defaultDeps(), anonId, q.count, q.includeMap === "1"),
  );
});
