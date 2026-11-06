"use client";

import type { FeedItem } from "@/lib/feedTypes";
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
}: {
  item: FeedItem;
  index: number;
  active: boolean;
  mounted: boolean;
}) {
  return (
    <section className="slide" data-index={index} data-active={active} aria-label={item.scene.headline}>
      {mounted ? <Stage scene={item.scene} active={active} /> : null}
    </section>
  );
}
