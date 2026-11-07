import type { Reason } from "./types";

/** `reason` の表示名(設計書 §6.1)。recsys は `reason` だけを返し、表示名は Next.js が付ける。 */
export const REASON_LABELS: Record<Reason, string> = {
  first: "最初の1本",
  explore_cold: "好みを探し中",
  near: "好みに近い",
  adventure: "冒険枠",
};

/** 配信の記録がない(`seenReset` で消えた)ときの表示 */
export const UNKNOWN_REASON_LABEL = "—";

export function reasonLabel(reason: string | null): string {
  if (reason !== null && Object.hasOwn(REASON_LABELS, reason)) return REASON_LABELS[reason as Reason];
  return UNKNOWN_REASON_LABEL;
}
