// POST /api/view と POST /api/like の中身(設計書 §6.2、§6.3)。DB と recsys への依存は `InteractDeps` で渡す。
import { z } from "zod";
import { getPool } from "./db";
import { HttpError } from "./http";
import {
  insertLike,
  insertView,
  loadDuration,
  loadVideoLogInfo,
  type VideoLogInfo,
} from "./queries/actions";
import { type ClusterRow, loadClusters } from "./queries/clusters";
import { loadEvents } from "./queries/events";
import { countViews, type LogRow, loadViewLog } from "./queries/log";
import { reasonLabel } from "./reasons";
import { recsysTaste } from "./recsys-client";
import { buildTaste, LOG_LIMIT } from "./taste";
import type {
  RecsysEvent,
  RecsysTasteRequest,
  RecsysTasteResponse,
  Taste,
} from "./types";

export interface InteractDeps {
  loadDuration(videoId: string): Promise<number | null>;
  insertView(v: {
    viewId: string;
    anonId: string;
    videoId: string;
    watchedSec: number;
    ratio: number;
  }): Promise<boolean>;
  insertLike(v: {
    anonId: string;
    videoId: string;
    liked: boolean;
  }): Promise<boolean>;
  loadVideoLogInfo(
    anonId: string,
    videoId: string,
  ): Promise<VideoLogInfo | null>;
  loadEvents(anonId: string): Promise<RecsysEvent[]>;
  recsysTaste(req: RecsysTasteRequest): Promise<RecsysTasteResponse>;
  loadClusters(): Promise<ClusterRow[]>;
  countViews(anonId: string): Promise<number>;
  loadViewLog(anonId: string, limit: number): Promise<LogRow[]>;
}

export function defaultInteractDeps(): InteractDeps {
  const pool = getPool();
  return {
    loadDuration: (id) => loadDuration(pool, id),
    insertView: (v) => insertView(pool, v),
    insertLike: (v) => insertLike(pool, v),
    loadVideoLogInfo: (a, id) => loadVideoLogInfo(pool, a, id),
    loadEvents: (a) => loadEvents(pool, a),
    recsysTaste,
    loadClusters: () => loadClusters(pool),
    countViews: (a) => countViews(pool, a),
    loadViewLog: (a, n) => loadViewLog(pool, a, n),
  };
}

export const viewBody = z.object({
  viewId: z.uuid(),
  videoId: z.string().min(1),
  watchedSec: z.number().min(0),
});

export const likeBody = z.object({
  videoId: z.string().min(1),
  liked: z.boolean(),
});

/** 保存済みの `events` から `taste` を作る(`/api/feed` と同じ組み立て)。 */
async function currentTaste(
  deps: InteractDeps,
  anonId: string,
): Promise<Taste> {
  const events = await deps.loadEvents(anonId);
  const rec = await deps.recsysTaste({ events });
  const [clusters, eventCount, log] = await Promise.all([
    deps.loadClusters(),
    deps.countViews(anonId),
    deps.loadViewLog(anonId, LOG_LIMIT),
  ]);
  return buildTaste(rec.taste, clusters, eventCount, log);
}

export async function postView(
  deps: InteractDeps,
  anonId: string,
  body: z.infer<typeof viewBody>,
) {
  const duration = await deps.loadDuration(body.videoId);
  if (duration === null) throw new HttpError(400, "videoId: unknown video");
  if (body.watchedSec > duration * 10)
    throw new HttpError(400, "watchedSec: too large");
  const ratio = Math.min(1, body.watchedSec / duration);
  await deps.insertView({
    viewId: body.viewId,
    anonId,
    videoId: body.videoId,
    watchedSec: body.watchedSec,
    ratio,
  });
  const [taste, info] = await Promise.all([
    currentTaste(deps, anonId),
    deps.loadVideoLogInfo(anonId, body.videoId),
  ]);
  return {
    taste,
    logEntry: {
      videoId: body.videoId,
      headline: info?.headline ?? "",
      reasonLabel: reasonLabel(info?.reason ?? null),
      ratio,
      liked: info?.liked ?? false,
    },
  };
}

export async function postLike(
  deps: InteractDeps,
  anonId: string,
  body: z.infer<typeof likeBody>,
) {
  if ((await deps.loadDuration(body.videoId)) === null) {
    throw new HttpError(400, "videoId: unknown video");
  }
  await deps.insertLike({ anonId, videoId: body.videoId, liked: body.liked });
  return { taste: await currentTaste(deps, anonId) };
}
