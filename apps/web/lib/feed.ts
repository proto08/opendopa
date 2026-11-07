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
import { loadKnownTagIds, loadVideoIdsWithAllTags } from "./queries/tags";
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
    scopeIds?: string[],
  ): Promise<void>;
  loadKnownTagIds(ids: string[]): Promise<Set<string>>;
  loadVideoIdsWithAllTags(tagIds: string[]): Promise<string[]>;
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
    recordImpressions: (a, p, r, s) => recordImpressions(pool, a, p, r, s),
    loadKnownTagIds: (ids) => loadKnownTagIds(pool, ids),
    loadVideoIdsWithAllTags: (ids) => loadVideoIdsWithAllTags(pool, ids),
    loadClusters: () => loadClusters(pool),
    loadMapPoints: () => loadMapPoints(pool),
    loadViewLog: (a, n) => loadViewLog(pool, a, n),
    countViews: (a) => countViews(pool, a),
  };
}

/** 絞り込みに使えるタグの最大数(hashtag_design.md §5.2) */
export const MAX_TAGS = 4;

/**
 * クエリ文字列(`count` は 1〜3、`includeMap` は 0 / 1、`tag` は繰り返せて 4 個まで。外れたら 400)。
 * `tag` は重複を除いた配列になる。
 */
export const feedQuery = z.object({
  count: z.coerce.number().int().min(1).max(3).default(1),
  includeMap: z.enum(["0", "1"]).default("0"),
  tag: z
    .union([z.string().min(1), z.array(z.string().min(1))])
    .optional()
    .transform((v) => [...new Set(v === undefined ? [] : [v].flat())])
    .pipe(z.array(z.string()).max(MAX_TAGS, `tag は ${MAX_TAGS} 個まで`)),
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
  tags: string[] = [],
): Promise<FeedResponse> {
  // 絞り込み: 未知のタグは 400。指定したすべてのタグを持つ動画(AND)だけを recsys の候補にする
  let candidateIds: string[] | undefined;
  if (tags.length > 0) {
    const known = await deps.loadKnownTagIds(tags);
    const unknown = tags.filter((t) => !known.has(t));
    if (unknown.length > 0)
      throw new HttpError(400, `tag: unknown tag ${unknown.join(", ")}`);
    candidateIds = await deps.loadVideoIdsWithAllTags(tags);
  }
  const [events, impressions] = await Promise.all([
    deps.loadEvents(anonId),
    deps.loadImpressions(anonId),
  ]);
  const rec = await deps.recsysFeed({
    events,
    seenIds: impressions.seenIds,
    recentDatasets: impressions.recentDatasets,
    ...(candidateIds && { candidateIds }),
    count,
  });
  if (rec.reason === "pool_empty") {
    return await withTaste(deps, anonId, rec, [], includeMap, "pool_empty");
  }

  const videos = await deps.loadVideos(rec.picks.map((p) => p.videoId));
  // recsys の索引が DB より古く、公開で消えた・除外された動画は配信しない
  const picks = rec.picks.filter((p) => videos.has(p.videoId));
  if (picks.length === 0) throw new HttpError(503, "no video available");
  // 絞り込み中の一巡(seenReset)は、候補の配信済みだけを消す(候補の外の配信済みは残す)
  if (candidateIds)
    await deps.recordImpressions(
      anonId,
      picks,
      rec.seenReset === true,
      candidateIds,
    );
  else await deps.recordImpressions(anonId, picks, rec.seenReset === true);

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

  return withTaste(deps, anonId, rec, items, includeMap);
}

/** `items` に `taste`(と地図)を足して返す */
async function withTaste(
  deps: FeedDeps,
  anonId: string,
  rec: RecsysFeedResponse,
  items: FeedItem[],
  includeMap: boolean,
  reason?: "pool_empty",
): Promise<FeedResponse> {
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
  if (reason) res.reason = reason;
  return res;
}
