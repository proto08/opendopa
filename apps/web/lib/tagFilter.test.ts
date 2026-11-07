import { describe, expect, it } from "vitest";
import {
  feedUrl,
  filteredCount,
  highlightPieces,
  MAX_TAGS,
  readTagsFromSearch,
  sameTags,
  sheetSections,
  type TagInfo,
  toggleTag,
  withTagsInSearch,
} from "./tagFilter";

const tag = (
  id: string,
  label: string,
  yomi: string,
  count: number,
): TagInfo => ({
  id,
  kind: id.startsWith("dataset:") ? "dataset" : "region",
  label,
  yomi,
  count,
});
const catalog: TagInfo[] = [
  tag("dataset:rental", "レンタカー", "れんたかー", 10),
  tag("dataset:accident", "事故", "じこ", 30),
  tag("dataset:empty", "空き", "あき", 0),
  tag("region:hokkaido", "北海道", "ほっかいどう", 42),
  tag("region:okinawa", "沖縄県", "おきなわけん", 7),
  ...Array.from({ length: 10 }, (_, i) =>
    tag(`region:r${i}`, `県${i}`, `けん${i}`, i + 1),
  ),
];

describe("URL", () => {
  it("tag を全部読み、重複は除き、上限で切る", () => {
    expect(readTagsFromSearch("?tag=a:1&tag=b:2&tag=a:1&x=1")).toEqual([
      "a:1",
      "b:2",
    ]);
    expect(readTagsFromSearch("")).toEqual([]);
    expect(readTagsFromSearch("?tag=")).toEqual([]);
    const many = ["a", "b", "c", "d", "e"].map((t) => `tag=${t}`).join("&");
    expect(readTagsFromSearch(many)).toHaveLength(MAX_TAGS);
  });
  it("他のクエリを残して tag だけ置き換える。空なら tag を消す", () => {
    expect(withTagsInSearch("?x=1&tag=old", ["region:hokkaido"])).toBe(
      "?x=1&tag=region%3Ahokkaido",
    );
    expect(withTagsInSearch("?tag=old", [])).toBe("");
    expect(withTagsInSearch("?x=1&tag=old", [])).toBe("?x=1");
  });
  it("feedUrl は tag を繰り返し、includeMap は 1 のときだけ", () => {
    expect(feedUrl(2, true, [])).toBe("/api/feed?count=2&includeMap=1");
    expect(feedUrl(1, false, ["dataset:rental", "region:hokkaido"])).toBe(
      "/api/feed?count=1&tag=dataset%3Arental&tag=region%3Ahokkaido",
    );
  });
});

describe("toggleTag", () => {
  it("あれば外し、なければ足し、上限では足さない", () => {
    expect(toggleTag(["a"], "b")).toEqual(["a", "b"]);
    expect(toggleTag(["a", "b"], "a")).toEqual(["b"]);
    expect(toggleTag(["a", "b", "c", "d"], "e")).toEqual(["a", "b", "c", "d"]);
  });
  it("sameTags は並びまで比べる", () => {
    expect(sameTags(["a", "b"], ["a", "b"])).toBe(true);
    expect(sameTags(["a", "b"], ["b", "a"])).toBe(false);
  });
});

describe("filteredCount", () => {
  it("選んだタグの件数の最小値。表にないタグ・未選択・表なしは null", () => {
    expect(filteredCount(["dataset:rental", "region:hokkaido"], catalog)).toBe(
      10,
    );
    expect(filteredCount(["nope"], catalog)).toBeNull();
    expect(filteredCount([], catalog)).toBeNull();
    expect(filteredCount(["dataset:rental"], null)).toBeNull();
  });
});

describe("sheetSections", () => {
  it("空入力: データの種類(件数順・0 件は除く)と、件数上位 8 件の地域", () => {
    const [datasets, regions] = sheetSections("", catalog);
    expect(datasets.title).toBe("データの種類");
    expect(datasets.tags.map((t) => t.id)).toEqual([
      "dataset:accident",
      "dataset:rental",
    ]);
    expect(regions.title).toBe("件数の多い地域");
    expect(regions.tags).toHaveLength(8);
    expect(regions.tags[0].id).toBe("region:hokkaido");
  });
  it("入力あり: あいまい一致の 1 区画。0 件のタグは出さない", () => {
    const s = sheetSections("北海", catalog);
    expect(s).toHaveLength(1);
    expect(s[0].tags.map((t) => t.id)).toEqual(["region:hokkaido"]);
    expect(sheetSections("あき", catalog)).toEqual([]);
  });
  it("一致なしは空(案内は画面が出す)", () => {
    expect(sheetSections("ぜんぜん", catalog)).toEqual([]);
  });
});

describe("highlightPieces", () => {
  it("一致した部分を分ける", () => {
    expect(highlightPieces("北海道", "北海")).toEqual([
      { text: "北海", match: true },
      { text: "道", match: false },
    ]);
    expect(highlightPieces("北海道", "海道")).toEqual([
      { text: "北", match: false },
      { text: "海道", match: true },
    ]);
  });
  it("カタカナと全角・半角のゆれを吸収する", () => {
    expect(highlightPieces("レンタカー", "れんた")).toEqual([
      { text: "レンタ", match: true },
      { text: "カー", match: false },
    ]);
  });
  it("連続して一致しなければ強調しない。空入力も", () => {
    expect(highlightPieces("北海道", "北道")).toEqual([
      { text: "北海道", match: false },
    ]);
    expect(highlightPieces("北海道", "")).toEqual([
      { text: "北海道", match: false },
    ]);
  });
});
