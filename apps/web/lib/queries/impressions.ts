import type { PoolClient } from "pg";
import type { Queryable } from "./db";
import type { Reason } from "../types";

/** recsys に渡す「直近に配信したデータセット」の最大件数 */
const RECENT_LIMIT = 50;

export interface Impressions {
  /** 配信済みの動画 ID */
  seenIds: string[];
  /** 配信済みのデータセット(新しい順。同じデータセットが続けば重複する) */
  recentDatasets: string[];
}

export async function loadImpressions(db: Queryable, anonId: string): Promise<Impressions> {
  const { rows } = await db.query<{ video_id: string; dataset_id: string }>(
    `SELECT i.video_id, v.dataset_id
       FROM impressions i JOIN videos v ON v.id = i.video_id
      WHERE i.anon_id = $1
      ORDER BY i.served_at DESC, i.id DESC`,
    [anonId],
  );
  return {
    seenIds: rows.map((r) => r.video_id),
    recentDatasets: rows.slice(0, RECENT_LIMIT).map((r) => r.dataset_id),
  };
}

/** トランザクションを張れるもの(`Pool`) */
export interface Connectable extends Queryable {
  connect(): Promise<Pick<PoolClient, "query" | "release">>;
}

/**
 * 配信した動画を記録する。`reset` なら先にそのユーザーの `impressions` を削除する(`seenReset`、#40)。
 * `UNIQUE (anon_id, video_id)` の競合(同時リクエストなど)は無視する。
 */
export async function recordImpressions(
  pool: Connectable,
  anonId: string,
  picks: { videoId: string; reason: Reason }[],
  reset: boolean,
): Promise<void> {
  if (!reset && picks.length === 0) return;
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    if (reset) await client.query("DELETE FROM impressions WHERE anon_id = $1", [anonId]);
    for (const p of picks) {
      await client.query(
        `INSERT INTO impressions (anon_id, video_id, reason) VALUES ($1, $2, $3)
         ON CONFLICT (anon_id, video_id) DO NOTHING`,
        [anonId, p.videoId, p.reason],
      );
    }
    await client.query("COMMIT");
  } catch (e) {
    await client.query("ROLLBACK").catch(() => {});
    throw e;
  } finally {
    client.release();
  }
}
