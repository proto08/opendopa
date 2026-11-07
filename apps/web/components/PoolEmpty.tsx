"use client";

import "./tags.css";

/** 絞り込みの候補がないとき、ステージの中に出す案内(`pool_empty`)。クリックは一時停止に伝えない */
export function PoolEmpty({ onClear }: { onClear: () => void }) {
  return (
    <div
      className="poolEmpty"
      role="status"
      onClick={(e) => e.stopPropagation()}
    >
      <p className="poolEmptyText">
        見終わりました。この条件の動画はありません。
      </p>
      <button type="button" className="poolEmptyButton" onClick={onClear}>
        タグを全部外す
      </button>
    </div>
  );
}
