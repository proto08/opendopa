import type { FlowComment } from "@opendopa/shared";
import type { CSSProperties } from "react";
import { activeComments } from "@/lib/comments";

/** 右から左へ流れるコメント。`comments` が空なら何も出さない */
export function Comments({
  comments,
  totalSec,
  playedSec,
}: {
  comments: FlowComment[];
  totalSec: number;
  playedSec: number;
}) {
  const active = activeComments(comments, totalSec, playedSec);
  if (active.length === 0) return null;
  return (
    <div className="comments" aria-hidden="true">
      {active.map((c) => (
        <span
          key={c.key}
          className="comment"
          data-style={c.style}
          style={{ "--lane": c.lane, "--p": c.progress } as CSSProperties}
        >
          {c.text}
        </span>
      ))}
    </div>
  );
}
