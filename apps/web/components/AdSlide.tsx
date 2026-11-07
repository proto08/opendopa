"use client";

import type { CSSProperties } from "react";
import type { Ad } from "@/lib/ads";
import "./ad.css";

/**
 * フィードの途中に入る、広告風の 1 画面(#147)。
 * 視聴の記録・いいね・好みの学習には関わらない(Stage を使わず、`/api/*` も呼ばない)。
 * 動画ではないので「AI生成」のラベルは出さず、広告であることを示す。
 */
export function AdSlide({
  ad,
  index,
  onNext,
}: {
  ad: Ad;
  index: number;
  onNext: () => void;
}) {
  return (
    <section
      className="slide"
      data-index={index}
      data-kind="ad"
      aria-label={`広告: ${ad.title}`}
    >
      <div className="adStage" style={{ "--cat": ad.color } as CSSProperties}>
        <span className="adBadge">広告</span>
        <div className="adBody">
          <h2 className="adTitle">{ad.title}</h2>
          <p className="adText">{ad.body}</p>
          <p className="adNote">{ad.note}</p>
        </div>
        <button type="button" className="adSkip" onClick={onNext}>
          次の動画へ
        </button>
      </div>
    </section>
  );
}
