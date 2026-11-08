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
  /** 背景の画像(`public/` からの絶対パス)。無ければ色のグラデーションだけ */
  image?: string;
  /** 申込みなどのリンク(新しいタブで開く。無ければボタンを出さない) */
  link?: { href: string; label: string };
};

export const ADS: readonly Ad[] = [
  {
    id: "tyrano-cup",
    link: {
      href: "https://hackz-community.doorkeeper.jp/events/200137",
      label: "申込みはこちら",
    },
    image: "/ads/hack.webp",
    title: "ハックツハッカソン ~ティラノカップ~ 2026.12",
    body: "2026-12-19(土)10:00 - 12-20(日)19:00 JST / グローバルアリーナ(福岡県宗像市吉留46-1)",
    note: "アスリート部門・カジュアル部門(各 無料) / 申込締切 12月1日 23:55 / あと40人参加できます",
    color: "#ff7a59",
  },
  {
    id: "gogo-hackathon",
    link: {
      href: "https://58hackathon.connpass.com/event/405339/",
      label: "申込みはこちら",
    },
    image: "/ads/58.webp",
    title: "58ハッカソン",
    body: "ProgateとGONENGOが主催。12〜25歳の生徒・学生が、短期間でプロダクトの企画・開発・発表を行います。2026-11-28(土)11:00 - 11-29(日)18:00 / 京都工芸繊維大学",
    note: "対象: 中学校・高校・高専・専門学校・大学・大学院の生徒・学生(12歳〜25歳)",
    color: "#3aa6c9",
  },
  {
    id: "links-hackathon",
    link: {
      href: "https://connpass.com/event/411586/",
      label: "申込みはこちら",
    },
    image: "/ads/links.png",
    title: "LINKS:POWER of DATA x DATA 2026 ハッカソン",
    body: "【国土交通省主催|参加無料】オープンデータと生成AIで挑む2日間。地域の移動手段、空き家、ドローン活用など、国土交通分野の社会課題に挑みます。",
    note: "2026-11-28(土)・29(日) / 麻布台ヒルズ 森JPタワー35階(予定) / 優秀チームは国土交通省 Project LINKS チームと意見交換 / 参加者に AWS アカウントを提供",
    color: "#2a9d8f",
  },
  {
    id: "claude-code-course",
    link: {
      href: "https://progate.com/courses/feature/claude-code",
      label: "コースを見る",
    },
    image: "/ads/claude-course.webp",
    title: "Claude Code 入門",
    body: "AI への仕事の依頼から、コードベースの調査、計画、実装、検証、引き継ぎまで。社内依頼管理アプリの改善を題材に、Coding Agent と開発を進める考え方を学びます。",
    note: "AGENTS.md・Skill・権限・Hook による運用の設計も学べるコース(Progate)",
    color: "#f08a5d",
  },
  {
    id: "progate-rust",
    link: {
      href: "https://progate.com/courses/feature/rust",
      label: "コースを見る",
    },
    image: "/ads/progate-rust.webp",
    title: "Rust",
    body: "メモリ安全性と速度を両立したプログラミング言語。所有権・借用という独自の仕組みで、null 参照やデータ競合をコンパイル時に防ぎます。",
    note: "基礎から、所有権・参照・構造体・enum と match・Result・イテレータ・ジェネリクス・トレイト・ライフタイムまで体系的に学べるコース(Progate)",
    color: "#d9724f",
  },
  {
    id: "progate-student-discount",
    link: {
      href: "https://progate.com/blogs/student-discount-release-20261016",
      label: "詳しく見る",
    },
    image: "/ads/progate-hello.webp",
    title: "Progate に学割が登場",
    body: "学校のメールアドレスを認証すると、プロプランが 75% OFF。AI や React、実務に近いコースまで、すべてのレッスンとコースが使えます。",
    note: "月額 1,248 円、年額なら月あたり 623 円 / 割引は申し込みから最大 4 年間続きます",
    color: "#3fb8a0",
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
