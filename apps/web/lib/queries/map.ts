import type { Queryable } from "./db";

export interface MapPoint {
  videoId: string;
  datasetId: string;
  x: number;
  y: number;
  clusterId: number | null;
}

/** 地図の点。配信できる動画(`status = 'ok'`)だけ。 */
export async function loadMapPoints(db: Queryable): Promise<MapPoint[]> {
  const { rows } = await db.query<{
    video_id: string;
    dataset_id: string;
    x: number;
    y: number;
    cluster_id: number | null;
  }>(
    `SELECT e.video_id, v.dataset_id, e.x, e.y, e.cluster_id
       FROM embeddings e JOIN videos v ON v.id = e.video_id
      WHERE v.status = 'ok'
      ORDER BY e.video_id`,
  );
  return rows.map((r) => ({
    videoId: r.video_id,
    datasetId: r.dataset_id,
    x: r.x,
    y: r.y,
    clusterId: r.cluster_id,
  }));
}
