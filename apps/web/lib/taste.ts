// `taste`(設計書 §6.4)の組み立て。`x`・`y`・`shares[].pct` は recsys の値をそのまま使い、
// 名前・色・要約文・視聴の記録を足す。
import type { ClusterRow } from "./queries/clusters";
import type { LogRow } from "./queries/log";
import { reasonLabel } from "./reasons";
import type { RecsysTaste, Taste } from "./types";

/** 要約文で「最後まで見る人」と言い切る、最大の割合のしきい値(%) */
export const SUMMARY_MIN_PCT = 40;
export const LOG_LIMIT = 6;

export function tasteSummary(
  eventCount: number,
  shares: { name: string; pct: number }[],
): string {
  if (eventCount === 0) return "まだ見ていないので、好みはわかりません";
  const top = shares.reduce<{ name: string; pct: number } | undefined>(
    (best, s) => (best === undefined || s.pct > best.pct ? s : best),
    undefined,
  );
  if (top && top.pct >= SUMMARY_MIN_PCT) return `あなたは「${top.name}」を最後まで見る人です`;
  return "好みはまだ決まっていません。いろいろ見ています";
}

export function buildTaste(
  recsys: RecsysTaste,
  clusters: readonly ClusterRow[],
  eventCount: number,
  log: readonly LogRow[],
): Taste {
  const byId = new Map(clusters.map((c) => [c.id, c]));
  const shares = recsys.shares.map((s) => {
    const c = byId.get(s.clusterId);
    return { clusterId: s.clusterId, name: c?.name ?? "", color: c?.color ?? "#999999", pct: s.pct };
  });
  return {
    x: recsys.x,
    y: recsys.y,
    shares,
    summary: tasteSummary(eventCount, shares),
    eventCount,
    log: log.slice(0, LOG_LIMIT).map((l) => ({
      videoId: l.videoId,
      headline: l.headline,
      reasonLabel: reasonLabel(l.reason),
      ratio: l.ratio,
      liked: l.liked,
    })),
  };
}
