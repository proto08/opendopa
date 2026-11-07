import type { Queryable } from "./db";

/** 動画の長さ(秒)。存在しない・配信対象でない(`status != 'ok'`)なら null。 */
export async function loadDuration(
  db: Queryable,
  videoId: string,
): Promise<number | null> {
  const { rows } = await db.query<{ duration_sec: number }>(
    "SELECT duration_sec FROM videos WHERE id = $1 AND status = 'ok'",
    [videoId],
  );
  return rows[0] ? Number(rows[0].duration_sec) : null;
}

/** 視聴を保存する。`view_id` が重複なら保存しない(false を返す)。 */
export async function insertView(
  db: Queryable,
  v: {
    viewId: string;
    anonId: string;
    videoId: string;
    watchedSec: number;
    ratio: number;
  },
): Promise<boolean> {
  const { rows } = await db.query(
    `INSERT INTO view_events (view_id, anon_id, video_id, watched_sec, ratio)
     VALUES ($1, $2, $3, $4, $5)
     ON CONFLICT (view_id) DO NOTHING
     RETURNING id`,
    [v.viewId, v.anonId, v.videoId, v.watchedSec, v.ratio],
  );
  return rows.length > 0;
}

/** 専用の接続を借りられるもの(`pg` の `Pool` がそのまま当てはまる)。トランザクションに使う。 */
export interface Connectable {
  connect(): Promise<Queryable & { release(): void }>;
}

/**
 * いいねの状態を保存する。そのユーザー・動画の最新の状態と同じなら追加しない(false を返す)。
 * 履歴がないときの最新の状態は「いいねなし(false)」として扱う。
 * 同じユーザーの同時リクエストで二重に足さないよう、1 つのトランザクションの中で
 * (anon_id, video_id) の advisory lock を取り、そのあとの別の文で最新の状態を読む
 * (READ COMMITTED では文ごとにスナップショットが取り直されるので、ロック待ちのあとでも先行のコミットが見える)。
 */
export async function insertLike(
  db: Connectable,
  v: { anonId: string; videoId: string; liked: boolean },
): Promise<boolean> {
  const client = await db.connect();
  try {
    await client.query("BEGIN");
    await client.query(
      "SELECT pg_advisory_xact_lock(hashtextextended($1 || ':' || $2, 0))",
      [v.anonId, v.videoId],
    );
    const { rows: latest } = await client.query<{ liked: boolean }>(
      `SELECT liked FROM like_events
        WHERE anon_id = $1 AND video_id = $2
        ORDER BY created_at DESC, id DESC LIMIT 1`,
      [v.anonId, v.videoId],
    );
    const current = latest[0]?.liked ?? false;
    let inserted = false;
    if (current !== v.liked) {
      await client.query(
        "INSERT INTO like_events (anon_id, video_id, liked) VALUES ($1, $2, $3)",
        [v.anonId, v.videoId, v.liked],
      );
      inserted = true;
    }
    await client.query("COMMIT");
    return inserted;
  } catch (e) {
    await client.query("ROLLBACK").catch(() => {});
    throw e;
  } finally {
    client.release();
  }
}

export interface VideoLogInfo {
  headline: string;
  reason: string | null;
  liked: boolean;
}

/** 視聴の記録 1 件ぶんの表示用の情報(見出し、出た理由、最新のいいね状態)。動画がなければ null。 */
export async function loadVideoLogInfo(
  db: Queryable,
  anonId: string,
  videoId: string,
): Promise<VideoLogInfo | null> {
  const { rows } = await db.query<{
    headline: string;
    reason: string | null;
    liked: boolean;
  }>(
    `SELECT v.headline, i.reason,
            COALESCE((SELECT l.liked FROM like_events l
                       WHERE l.anon_id = $1 AND l.video_id = v.id
                       ORDER BY l.created_at DESC, l.id DESC LIMIT 1), false) AS liked
       FROM videos v
       LEFT JOIN impressions i ON i.anon_id = $1 AND i.video_id = v.id
      WHERE v.id = $2`,
    [anonId, videoId],
  );
  return rows[0] ?? null;
}
