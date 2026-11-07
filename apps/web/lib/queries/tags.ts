import type { Queryable } from "./db";

export interface TagRow {
  id: string;
  kind: string;
  label: string;
  yomi: string;
  /** `status = 'ok'` の動画の本数 */
  count: number;
}

/** 全タグと件数(設計 hashtag_design.md §5.1)。`excluded` の動画は数えない。動画がないタグは 0。 */
export async function loadTags(db: Queryable): Promise<TagRow[]> {
  const { rows } = await db.query<Omit<TagRow, "count"> & { count: string }>(
    `SELECT t.id, t.kind, t.label, t.yomi, count(v.id) AS count
       FROM tags t
       LEFT JOIN video_tags vt ON vt.tag_id = t.id
       LEFT JOIN videos v ON v.id = vt.video_id AND v.status = 'ok'
      GROUP BY t.id
      ORDER BY t.sort, t.id`,
  );
  return rows.map((r) => ({ ...r, count: Number(r.count) }));
}

/** `ids` のうち、`tags` にある ID(未知の ID の検出用) */
export async function loadKnownTagIds(
  db: Queryable,
  ids: string[],
): Promise<Set<string>> {
  if (ids.length === 0) return new Set();
  const { rows } = await db.query<{ id: string }>(
    `SELECT id FROM tags WHERE id = ANY($1::text[])`,
    [ids],
  );
  return new Set(rows.map((r) => r.id));
}

/** `tagIds` のすべてを持つ(AND)、`status = 'ok'` の動画 ID(§5.2) */
export async function loadVideoIdsWithAllTags(
  db: Queryable,
  tagIds: string[],
): Promise<string[]> {
  const { rows } = await db.query<{ video_id: string }>(
    `SELECT vt.video_id
       FROM video_tags vt JOIN videos v ON v.id = vt.video_id
      WHERE vt.tag_id = ANY($1::text[]) AND v.status = 'ok'
      GROUP BY vt.video_id
     HAVING count(DISTINCT vt.tag_id) = $2`,
    [tagIds, tagIds.length],
  );
  return rows.map((r) => r.video_id);
}
