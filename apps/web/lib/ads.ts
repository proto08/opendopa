// フィードに差し込む広告風の画面(#147)。
// 広告は固定のデータで、DB にも `GET /api/feed` にも載せない。画面(Feed)が動画の列に差し込むだけなので、
// 視聴・いいね・スキップは `/api/view` `/api/like` に送られず、好みの学習(recsys)にも届かない。
import type { FeedItem } from "./feedTypes";

export type Ad = {
  id: string;
  /** 見出し(大きく出す) */
  title: string;
  body: string;
  /** 日付や場所など、補足の 1 行 */
  note: string;
  /** 背景のアクセント色 */
  color: string;
};

export const ADS: readonly Ad[] = [
  {
    id: "hackathon",
    title: "OpenDopa ハッカソン",
    body: "国土交通省のオープンデータで、縦スクロールの動画を作ろう。",
    note: "2026-11-07〜08",
    color: "#ff7a59",
  },
  {
    id: "project-links",
    title: "Project LINKS",
    body: "データと人をつなぐ取り組みのお知らせ枠です。",
    note: "※ 広告枠のサンプル表示",
    color: "#3aa6c9",
  },
];

/** 動画が何本ごとに広告を 1 つ差し込むか */
export const AD_EVERY = 5;

export type Slot = { kind: "video"; item: FeedItem } | { kind: "ad"; ad: Ad };

/**
 * 動画の列に広告を差し込む。動画が `every` 本続くごとに、次の動画の前に 1 つ入れる
 * (次の動画がまだないときは入れない。末尾に広告だけが残らない)。広告は ADS を順に回す。
 */
export function buildSlots(
  items: readonly FeedItem[],
  every: number = AD_EVERY,
  ads: readonly Ad[] = ADS,
): Slot[] {
  const slots: Slot[] = [];
  let adCount = 0;
  items.forEach((item, i) => {
    if (ads.length > 0 && every > 0 && i > 0 && i % every === 0) {
      slots.push({ kind: "ad", ad: ads[adCount % ads.length] as Ad });
      adCount++;
    }
    slots.push({ kind: "video", item });
  });
  return slots;
}
