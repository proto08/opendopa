// ダミーの /api/feed の中身。好みの計算は使わず、DB から(なければフィクスチャから)ランダムに返す。
// 本物は #47 で置き換える。
import { validateScene } from "@opendopa/shared";
import accident from "@opendopa/shared/fixtures/accident-0001.json";
import mapPoints from "@opendopa/shared/fixtures/map-points.json";
import mapPolygon from "@opendopa/shared/fixtures/map-polygon.json";
import mapRoute from "@opendopa/shared/fixtures/map-route.json";
import { getPool } from "./db";
import type { FeedItem } from "./feedTypes";

export const REASON_LABELS: Record<FeedItem["reason"], string> = {
  first: "最初の1本",
  explore_cold: "好みを探し中",
  near: "好みに近い",
  adventure: "冒険枠",
};

const fixtureFiles = [accident, mapPoints, mapPolygon, mapRoute];

export function fixtureItems(): FeedItem[] {
  return fixtureFiles.map((json) => {
    const r = validateScene(json);
    if (!r.ok) throw new Error(`フィクスチャが不正: ${r.errors.join(", ")}`);
    const { scene } = r;
    return {
      videoId: scene.videoId,
      reason: "explore_cold",
      reasonLabel: REASON_LABELS.explore_cold,
      scene,
      csvRow: [
        ["見出し", scene.headline],
        ["データ名", scene.source.datasetName],
      ],
      sourceRef: scene.source.ref,
    };
  });
}

/** 配列から重複なしでランダムに n 件(足りなければ繰り返して埋める) */
export function pickRandom<T>(all: readonly T[], n: number, rand: () => number = Math.random): T[] {
  if (all.length === 0) return [];
  const out: T[] = [];
  while (out.length < n) {
    const pool = [...all];
    while (pool.length > 0 && out.length < n) {
      out.push(pool.splice(Math.floor(rand() * pool.length), 1)[0]);
    }
  }
  return out;
}

type VideoRow = {
  scene: unknown;
  csv_row: [string, string][];
  source_ref: string;
};

async function dbItems(count: number): Promise<FeedItem[]> {
  if (!process.env.DATABASE_URL) return [];
  try {
    const { rows } = await getPool().query<VideoRow>(
      "SELECT scene, csv_row, source_ref FROM videos WHERE status = 'ok' ORDER BY random() LIMIT $1",
      [count],
    );
    const items: FeedItem[] = [];
    for (const row of rows) {
      const r = validateScene(row.scene);
      if (!r.ok) continue;
      items.push({
        videoId: r.scene.videoId,
        reason: "explore_cold",
        reasonLabel: REASON_LABELS.explore_cold,
        scene: r.scene,
        csvRow: row.csv_row,
        sourceRef: row.source_ref,
      });
    }
    return items;
  } catch {
    return [];
  }
}

export async function dummyFeed(count: number): Promise<FeedItem[]> {
  const fromDb = await dbItems(count);
  if (fromDb.length > 0) return fromDb;
  return pickRandom(fixtureItems(), count);
}

/** `count` を 1〜3 に丸める(設計書 §6.1)。不正なら 1 */
export function parseCount(raw: string | null): number {
  const n = Number(raw);
  if (!Number.isInteger(n)) return 1;
  return Math.min(Math.max(n, 1), 3);
}
