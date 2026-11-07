import type { RecsysEvent } from "../types";
import type { Queryable } from "./db";

interface EventRow {
  type: "view" | "like";
  video_id: string;
  ratio: number | null;
  liked: boolean | null;
}

/**
 * そのユーザーの視聴といいねを時刻順に返す(設計書 §6.1)。
 * 同じ時刻なら `id` 順、それも同じなら視聴を先にする(二つのテーブルの `id` は別の連番)。
 */
export async function loadEvents(
  db: Queryable,
  anonId: string,
): Promise<RecsysEvent[]> {
  const { rows } = await db.query<EventRow>(
    `SELECT type, video_id, ratio, liked FROM (
       SELECT 'view' AS type, video_id, ratio, NULL::boolean AS liked, created_at, id
         FROM view_events WHERE anon_id = $1
       UNION ALL
       SELECT 'like' AS type, video_id, NULL::real AS ratio, liked, created_at, id
         FROM like_events WHERE anon_id = $1
     ) e
     ORDER BY created_at, id, type DESC`,
    [anonId],
  );
  return rows.map((r) =>
    r.type === "view"
      ? { type: "view", videoId: r.video_id, ratio: Number(r.ratio) }
      : { type: "like", videoId: r.video_id, liked: Boolean(r.liked) },
  );
}
