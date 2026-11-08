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
        {ad.image && (
          // 画像は上の領域だけに置き、文字とは重ねない。装飾なので alt は空。
          // 固定の 1 枚で最適化が要らないので next/image は使わない
          // biome-ignore lint/performance/noImgElement: 固定の画像
          <img className="adImage" src={ad.image} alt="" />
        )}
        <div className="adBody">
          <span className="adBadge">広告</span>
          <h2 className="adTitle">{ad.title}</h2>
          <p className="adText">{ad.body}</p>
          <p className="adNote">{ad.note}</p>
          <div className="adActions">
            {ad.link && (
              <a
                className="adLink"
                href={ad.link.href}
                target="_blank"
                rel="noopener noreferrer"
              >
                {ad.link.label}
              </a>
            )}
            <button type="button" className="adSkip" onClick={onNext}>
              次の動画へ
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
