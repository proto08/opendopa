// GET /api/tags の中身(設計 hashtag_design.md §5.1)。DB への依存は `TagsDeps` で渡す(テストで差し替える)。
import { getPool } from "./db";
import { loadTags, type TagRow } from "./queries/tags";

export interface TagsDeps {
  loadTags(): Promise<TagRow[]>;
}

export function defaultTagsDeps(): TagsDeps {
  const pool = getPool();
  return { loadTags: () => loadTags(pool) };
}

export type TagsResponse = { tags: TagRow[] };

export async function getTags(deps: TagsDeps): Promise<TagsResponse> {
  return { tags: await deps.loadTags() };
}
