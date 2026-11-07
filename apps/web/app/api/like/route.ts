import { connection } from "next/server";
import { apiHandler, json, parseJsonBody } from "@/lib/http";
import { defaultInteractDeps, likeBody, postLike } from "@/lib/interact";

// POST /api/like(設計書 §6.3)。トグルでなく状態を送る。
export const POST = apiHandler(async ({ anonId, req }) => {
  await connection();
  const body = await parseJsonBody(req, likeBody);
  return json(await postLike(defaultInteractDeps(), anonId, body));
});
