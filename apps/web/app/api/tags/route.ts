import { connection } from "next/server";
import { apiHandler, json } from "@/lib/http";
import { defaultTagsDeps, getTags } from "@/lib/tags";

// GET /api/tags(hashtag_design.md §5.1)。全タグと件数。
export const GET = apiHandler(async () => {
  await connection();
  return json(await getTags(defaultTagsDeps()));
});
