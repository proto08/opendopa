import type { Queryable } from "./db";

/** 動画の長さ(秒)。存在しない・配信対象でない(`status != 'ok'`)なら null。 */
export async function loadDuration(db: Queryable, videoId: string): Promise<number | null> {
  const { rows } = await db.query<{ duration_sec: number }>(
    "SELECT duration_sec FROM videos WHERE id = $1 AND status = 'ok'",
    [videoId],
  );
  return rows[0] ? Number(rows[0].duration_sec) : null;
}

/** 視聴を保存する。`view_id` が重複なら保存しない(false を返す)。 */
export async function insertView(
  db: Queryable,
  v: { viewId: string; anonId: string; videoId: string; watchedSec: number; ratio: number },
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

/**
 * いいねの状態を保存する。そのユーザー・動画の最新の状態と同じなら追加しない(false を返す)。
 * 履歴がないときの最新の状態は「いいねなし(false)」として扱う。
 * 同じユーザーの同時リクエストで二重に足さないよう、(anon_id, video_id) の advisory lock を取る。
 */
export async function insertLike(
  db: Queryable,
  v: { anonId: string; videoId: string; liked: boolean },
): Promise<boolean> {
  // 1 文で「最新の状態の判定」と追加を行う。同時実行の競合は advisory lock で直列化する
  const { rows } = await db.query(
    `WITH lock AS (SELECT pg_advisory_xact_lock(hashtextextended($1 || ':' || $2, 0))),
     latest AS (
       SELECT COALESCE((SELECT liked FROM like_events
                         WHERE anon_id = $1 AND video_id = $2
                         ORDER BY created_at DESC, id DESC LIMIT 1), false) AS liked
         FROM lock
     )
     INSERT INTO like_events (anon_id, video_id, liked)
     SELECT $1, $2, $3 FROM latest WHERE latest.liked <> $3
     RETURNING id`,
    [v.anonId, v.videoId, v.liked],
  );
  return rows.length > 0;
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
  const { rows } = await db.query<{ headline: string; reason: string | null; liked: boolean }>(
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
