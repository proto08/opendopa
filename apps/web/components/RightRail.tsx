"use client";

import "./rail.css";

/** ステージの右端のボタン(設計書 §3.3)。クリックはステージの一時停止/再開に伝えない(キーは止めない: ボタンにフォーカスがあっても l や j を効かせる) */
export function RightRail({
  liked,
  onLike,
  onCsv,
  onTaste,
  onNext,
}: {
  liked: boolean;
  onLike: () => void;
  onCsv: () => void;
  onTaste: () => void;
  onNext: () => void;
}) {
  return (
    <div
      className="rail"
      role="group"
      aria-label="操作"
      onClick={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        className="railButton"
        data-kind="like"
        data-liked={liked}
        aria-pressed={liked}
        aria-label="いいね(L)"
        onClick={onLike}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M12 21s-7.5-4.6-9.6-9.2C.9 8.4 2.6 4.5 6.3 4.5c2.1 0 3.7 1.2 5.7 3.4 2-2.2 3.6-3.4 5.7-3.4 3.7 0 5.4 3.9 3.9 7.3C19.5 16.4 12 21 12 21z"
            fill={liked ? "currentColor" : "none"}
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      <button
        type="button"
        className="railButton"
        data-kind="csv"
        aria-label="元データ"
        onClick={onCsv}
      >
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
        >
          <rect x="4" y="4" width="16" height="16" rx="2" />
          <path d="M4 10h16M4 15h16M10 4v16" />
        </svg>
      </button>
      <button
        type="button"
        className="railButton railTaste"
        data-kind="taste"
        aria-label="好み"
        onClick={onTaste}
      >
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
        >
          <circle cx="12" cy="12" r="8" />
          <circle cx="12" cy="12" r="3" fill="currentColor" />
        </svg>
      </button>
      <button
        type="button"
        className="railButton"
        data-kind="next"
        aria-label="次へ(J)"
        onClick={onNext}
      >
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
    </div>
  );
}
