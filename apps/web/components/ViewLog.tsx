import { LOG_LIMIT } from "@/lib/taste";
import type { LogEntry } from "@/lib/types";

/** 最近の視聴(最大 6 件)。見出し、出た理由、視聴率、いいね */
export function ViewLog({ log }: { log: readonly LogEntry[] }) {
  if (log.length === 0)
    return <p className="viewLogEmpty">まだ視聴の記録はありません</p>;
  return (
    <ol className="viewLog" aria-label="最近の視聴">
      {log.slice(0, LOG_LIMIT).map((l, i) => (
        <li key={`${l.videoId}-${i}`} className="viewLogItem">
          <span className="viewLogHeadline">{l.headline}</span>
          <span className="viewLogMeta">
            <span className="viewLogReason">{l.reasonLabel}</span>
            <span className="viewLogRatio">
              視聴 {Math.round(l.ratio * 100)}%
            </span>
            {l.liked ? (
              <span className="viewLogLike" aria-label="いいね済み">
                ♥
              </span>
            ) : null}
          </span>
        </li>
      ))}
    </ol>
  );
}
