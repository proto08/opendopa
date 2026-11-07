import type { Queryable } from "./db";

export interface LogRow {
  videoId: string;
  headline: string;
  /** その動画の `impressions.reason`。配信の記録がなければ null */
  reason: string | null;
  ratio: number;
  liked: boolean;
}

/**
 * 右パネルの「視聴の記録」。新しい視聴から最大 `limit` 件。
 * `liked` はその動画の最新の `like_events` の状態(なければ false)。
 */
export async function loadViewLog(db: Queryable, anonId: string, limit: number): Promise<LogRow[]> {
  const { rows } = await db.query<{
    video_id: string;
    headline: string;
    reason: string | null;
    ratio: number;
    liked: boolean;
  }>(
    `SELECT w.video_id, v.headline, i.reason, w.ratio,
            COALESCE((SELECT l.liked FROM like_events l
                       WHERE l.anon_id = w.anon_id AND l.video_id = w.video_id
                       ORDER BY l.created_at DESC, l.id DESC LIMIT 1), false) AS liked
       FROM view_events w
       JOIN videos v ON v.id = w.video_id
       LEFT JOIN impressions i ON i.anon_id = w.anon_id AND i.video_id = w.video_id
      WHERE w.anon_id = $1
      ORDER BY w.created_at DESC, w.id DESC
      LIMIT $2`,
    [anonId, limit],
  );
  return rows.map((r) => ({
    videoId: r.video_id,
    headline: r.headline,
    reason: r.reason,
    ratio: Number(r.ratio),
    liked: r.liked,
  }));
}

/** `view_events` の件数(`taste.eventCount`) */
export async function countViews(db: Queryable, anonId: string): Promise<number> {
  const { rows } = await db.query<{ n: string }>(
    "SELECT count(*)::text AS n FROM view_events WHERE anon_id = $1",
    [anonId],
  );
  return Number(rows[0]?.n ?? 0);
}
