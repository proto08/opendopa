import type { Queryable } from "./db";

export interface ClusterRow {
  id: number;
  name: string;
  color: string;
  cx: number;
  cy: number;
}

export async function loadClusters(db: Queryable): Promise<ClusterRow[]> {
  const { rows } = await db.query<ClusterRow>(
    "SELECT id, name, color, cx, cy FROM clusters ORDER BY id",
  );
  return rows;
}
