"use client";

import type { Tag } from "@opendopa/shared";
import "./tags.css";

/** テロップの上のタグ(`#レンタカー #北海道`)。タップで絞り込み、もう一度で外す。クリックは一時停止に伝えない */
export function VideoTags({
  tags,
  selected,
  onTag,
}: {
  tags: Tag[];
  selected: readonly string[];
  onTag?: (id: string) => void;
}) {
  if (tags.length === 0) return null;
  return (
    <div
      className="videoTags"
      role="group"
      aria-label="タグ"
      onClick={(e) => e.stopPropagation()}
    >
      {tags.map((t) => (
        <button
          key={t.id}
          type="button"
          className="videoTag"
          data-kind={t.kind}
          data-selected={selected.includes(t.id)}
          aria-pressed={selected.includes(t.id)}
          onClick={() => onTag?.(t.id)}
        >
          #{t.label}
        </button>
      ))}
    </div>
  );
}
