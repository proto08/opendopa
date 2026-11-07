"use client";

import type { ReactNode } from "react";
import type { FeedItem } from "@/lib/feedTypes";
import { RightRail } from "./RightRail";
import { Stage } from "./Stage";

/**
 * フィードの 1 本分(1 画面)。ステージ(字幕・コメント・ラベル・出典を含む)を置く。
 * 離れた動画は、Stage を作らず場所だけ取る(見えていない動画の時計とコメントを動かさない)。
 */
export function Slide({
  item,
  index,
  active,
  mounted,
  hold,
  liked,
  onLike,
  onCsv,
  onTaste,
  onNext,
  selectedTags,
  onTag,
  overlay,
}: {
  item: FeedItem;
  index: number;
  active: boolean;
  mounted: boolean;
  /** シートが開いている間、再生を止める */
  hold: boolean;
  liked: boolean;
  onLike: () => void;
  onCsv: () => void;
  onTaste: () => void;
  onNext: () => void;
  selectedTags: readonly string[];
  onTag: (id: string) => void;
  /** 虫眼鏡と検索シート */
  overlay: ReactNode;
}) {
  return (
    <section
      className="slide"
      data-index={index}
      data-active={active}
      aria-label={item.scene.headline}
    >
      {mounted ? (
        <Stage
          scene={item.scene}
          active={active}
          hold={hold}
          selectedTags={selectedTags}
          onTag={onTag}
        >
          <RightRail
            liked={liked}
            onLike={onLike}
            onCsv={onCsv}
            onTaste={onTaste}
            onNext={onNext}
          />
          {overlay}
        </Stage>
      ) : null}
    </section>
  );
}
