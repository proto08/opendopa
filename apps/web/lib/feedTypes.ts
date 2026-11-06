import type { Scene } from "@opendopa/shared";

/** `GET /api/feed` の `items[]` の 1 件(設計書 §6.1)。本物の API(#47)も同じ形で返す */
export type FeedItem = {
  videoId: string;
  reason: "first" | "explore_cold" | "near" | "adventure";
  reasonLabel: string;
  scene: Scene;
  csvRow: [string, string][];
  sourceRef: string;
};

export type FeedResponse = { items: FeedItem[] };
