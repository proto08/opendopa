import type { Queryable } from "./db";

export interface VideoRow {
  id: string;
  headline: string;
  scene: unknown;
  csvRow: [string, string][];
  sourceRef: string;
}

/** 配信する動画の中身。`decisions`(判断モデルの記録)は読まない(設計書 §6.1)。 */
export async function loadVideos(
  db: Queryable,
  ids: string[],
): Promise<Map<string, VideoRow>> {
  if (ids.length === 0) return new Map();
  const { rows } = await db.query<{
    id: string;
    headline: string;
    scene: unknown;
    csv_row: [string, string][];
    source_ref: string;
  }>(
    `SELECT id, headline, scene, csv_row, source_ref FROM videos
      WHERE id = ANY($1::text[]) AND status = 'ok'`,
    [ids],
  );
  return new Map(
    rows.map((r) => [
      r.id,
      {
        id: r.id,
        headline: r.headline,
        scene: r.scene,
        csvRow: r.csv_row,
        sourceRef: r.source_ref,
      },
    ]),
  );
}
