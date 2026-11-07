// GET /api/feed の中身(設計書 §6.1)。DB と recsys への依存は `FeedDeps` で渡す(テストで差し替える)。
import type { Scene } from "@opendopa/shared";
import { z } from "zod";
import { getPool } from "./db";
import type { FeedItem, FeedMap, FeedResponse } from "./feedTypes";
import { HttpError } from "./http";
import { type ClusterRow, loadClusters } from "./queries/clusters";
import { loadEvents } from "./queries/events";
import {
  type Impressions,
  loadImpressions,
  recordImpressions,
} from "./queries/impressions";
import { countViews, type LogRow, loadViewLog } from "./queries/log";
import { loadMapPoints, type MapPoint } from "./queries/map";
import { loadVideos, type VideoRow } from "./queries/videos";
import { reasonLabel } from "./reasons";
import { recsysFeed } from "./recsys-client";
import { buildTaste, LOG_LIMIT } from "./taste";
import type {
  Reason,
  RecsysEvent,
  RecsysFeedRequest,
  RecsysFeedResponse,
} from "./types";

export interface FeedDeps {
  loadEvents(anonId: string): Promise<RecsysEvent[]>;
  loadImpressions(anonId: string): Promise<Impressions>;
  recsysFeed(req: RecsysFeedRequest): Promise<RecsysFeedResponse>;
  loadVideos(ids: string[]): Promise<Map<string, VideoRow>>;
  recordImpressions(
    anonId: string,
    picks: { videoId: string; reason: Reason }[],
    reset: boolean,
  ): Promise<void>;
  loadClusters(): Promise<ClusterRow[]>;
  loadMapPoints(): Promise<MapPoint[]>;
  loadViewLog(anonId: string, limit: number): Promise<LogRow[]>;
  countViews(anonId: string): Promise<number>;
}

export function defaultDeps(): FeedDeps {
  const pool = getPool();
  return {
    loadEvents: (a) => loadEvents(pool, a),
    loadImpressions: (a) => loadImpressions(pool, a),
    recsysFeed,
    loadVideos: (ids) => loadVideos(pool, ids),
    recordImpressions: (a, p, r) => recordImpressions(pool, a, p, r),
    loadClusters: () => loadClusters(pool),
    loadMapPoints: () => loadMapPoints(pool),
    loadViewLog: (a, n) => loadViewLog(pool, a, n),
    countViews: (a) => countViews(pool, a),
  };
}

/** クエリ文字列(`count` は 1〜3、`includeMap` は 0 / 1。外れたら 400) */
export const feedQuery = z.object({
  count: z.coerce.number().int().min(1).max(3).default(1),
  includeMap: z.enum(["0", "1"]).default("0"),
});

/** 配信しない `numbers`(検証用)を除いたシーン */
function stripNumbers(scene: unknown): Scene {
  const copy = { ...(scene as Record<string, unknown>) };
  delete copy.numbers;
  return copy as unknown as Scene;
}

function buildMap(points: MapPoint[], clusters: ClusterRow[]): FeedMap {
  return {
    points,
    clusters: clusters.map(({ id, name, color, cx, cy }) => ({
      id,
      name,
      color,
      cx,
      cy,
    })),
  };
}

export async function getFeed(
  deps: FeedDeps,
  anonId: string,
  count: number,
  includeMap: boolean,
): Promise<FeedResponse> {
  const [events, impressions] = await Promise.all([
    deps.loadEvents(anonId),
    deps.loadImpressions(anonId),
  ]);
  const rec = await deps.recsysFeed({
    events,
    seenIds: impressions.seenIds,
    recentDatasets: impressions.recentDatasets,
    count,
  });

  const videos = await deps.loadVideos(rec.picks.map((p) => p.videoId));
  // recsys の索引が DB より古く、公開で消えた・除外された動画は配信しない
  const picks = rec.picks.filter((p) => videos.has(p.videoId));
  if (picks.length === 0) throw new HttpError(503, "no video available");
  await deps.recordImpressions(anonId, picks, rec.seenReset === true);

  const items: FeedItem[] = picks.map((p) => {
    const v = videos.get(p.videoId)!;
    return {
      videoId: p.videoId,
      reason: p.reason,
      reasonLabel: reasonLabel(p.reason),
      scene: stripNumbers(v.scene),
      csvRow: v.csvRow,
      sourceRef: v.sourceRef,
    };
  });

  const [clusters, eventCount, log, points] = await Promise.all([
    deps.loadClusters(),
    deps.countViews(anonId),
    deps.loadViewLog(anonId, LOG_LIMIT),
    includeMap ? deps.loadMapPoints() : Promise.resolve(undefined),
  ]);
  const res: FeedResponse = {
    items,
    taste: buildTaste(rec.taste, clusters, eventCount, log),
  };
  if (points) res.map = buildMap(points, clusters);
  return res;
}
