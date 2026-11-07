"use client";

import "./tags.css";

/** ステージの左上、ロゴの下の虫眼鏡。絞り込み中は黄色にして「絞り込み中 N本」を出す */
export function SearchButton({
  filtering,
  count,
  onOpen,
}: {
  filtering: boolean;
  /** 絞り込み中の本数(分からなければ null) */
  count: number | null;
  onOpen: () => void;
}) {
  return (
    <div className="searchWrap" onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        className="searchButton"
        data-filtering={filtering}
        aria-label={
          filtering
            ? `タグで絞り込み中${count === null ? "" : `(${count}本)`}。検索を開く`
            : "タグで検索"
        }
        onClick={onOpen}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle
            cx="10.5"
            cy="10.5"
            r="6.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
          />
          <path
            d="M15.5 15.5 21 21"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
          />
        </svg>
        {filtering ? (
          <span className="searchLabel">
            絞り込み中{count === null ? "" : ` ${count}本`}
          </span>
        ) : null}
      </button>
    </div>
  );
}
