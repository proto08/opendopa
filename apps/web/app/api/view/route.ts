import { connection } from "next/server";
import { apiHandler, json, parseJsonBody } from "@/lib/http";
import { defaultInteractDeps, postView, viewBody } from "@/lib/interact";

// POST /api/view(設計書 §6.2)。sendBeacon は Content-Type が text/plain になるが、本文は JSON として読む。
export const POST = apiHandler(async ({ anonId, req }) => {
  await connection();
  const body = await parseJsonBody(req, viewBody);
  return json(await postView(defaultInteractDeps(), anonId, body));
});
