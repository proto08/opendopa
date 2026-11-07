// BFF の型(設計書 §6)。シーンJSON の型は `@opendopa/shared` を使う。

/** recsys に渡す、ユーザーの視聴といいねの履歴 1 件(§6.6)。時刻順に並べて渡す。 */
export type RecsysEvent =
  | { type: "view"; videoId: string; ratio: number }
  | { type: "like"; videoId: string; liked: boolean };

/** 選ばれた理由(§6.6)。表示名(`reasonLabel`)は Next.js が付ける。 */
export type Reason = "first" | "explore_cold" | "near" | "adventure";

export interface RecsysShare {
  clusterId: number;
  pct: number;
}

/** recsys が計算する `taste` の部分(§6.6)。 */
export interface RecsysTaste {
  x: number;
  y: number;
  shares: RecsysShare[];
}

export interface RecsysFeedRequest {
  events: RecsysEvent[];
  seenIds: string[];
  recentDatasets: string[];
  /** あれば、その動画だけから選ぶ(絞り込み。空なら `pool_empty`)。省略は全体から */
  candidateIds?: string[];
  count: number;
}

export interface RecsysFeedResponse {
  picks: { videoId: string; reason: Reason }[];
  /** 未視聴が尽きたので、`seenIds` を空として選んだ。`true` なら `impressions` を削除する(#40) */
  seenReset?: boolean;
  /** 候補が 1 本もないときだけ `"pool_empty"` */
  reason?: "pool_empty";
  taste: RecsysTaste;
}

export interface RecsysTasteRequest {
  events: RecsysEvent[];
}

export interface RecsysTasteResponse {
  taste: RecsysTaste;
}

export interface LogEntry {
  videoId: string;
  headline: string;
  reasonLabel: string;
  ratio: number;
  liked: boolean;
}

/** ブラウザに返す `taste`(§6.4)。 */
export interface Taste {
  x: number;
  y: number;
  shares: { clusterId: number; name: string; color: string; pct: number }[];
  summary: string;
  eventCount: number;
  log: LogEntry[];
}

/** エラーレスポンスの本文(§6.5)。 */
export interface ErrorBody {
  error: string;
}
