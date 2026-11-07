import type { Scene } from "@opendopa/shared";
import type { MapPoint } from "./queries/map";
import type { Reason, Taste } from "./types";

/** `GET /api/feed` の `items[]` の 1 件(設計書 §6.1)。`numbers`(検証用)は配信しないので、実際は入っていない */
export type FeedItem = {
  videoId: string;
  reason: Reason;
  reasonLabel: string;
  scene: Scene;
  csvRow: [string, string][];
  sourceRef: string;
};

export type FeedMap = {
  points: MapPoint[];
  clusters: { id: number; name: string; color: string; cx: number; cy: number }[];
};

export type FeedResponse = { items: FeedItem[]; taste: Taste; map?: FeedMap };
