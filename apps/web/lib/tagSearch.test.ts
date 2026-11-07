import { describe, expect, it } from "vitest";
import { normalize, scoreTag, searchTags } from "./tagSearch";

const hokkaido = { label: "北海道", yomi: "ほっかいどう", count: 42 };
const rental = { label: "レンタカー", yomi: "れんたかー", count: 10 };
const tags = [hokkaido, rental];

describe("normalize", () => {
  it("NFKC・小文字・カタカナ→ひらがな・空白除去", () => {
    expect(normalize(" ＡＢｃ　レンタ ")).toBe("abcれんた");
  });
});

describe("scoreTag", () => {
  it("前方一致は 4", () => expect(scoreTag("北海", hokkaido)).toBe(4));
  it("label の部分一致は 3", () => expect(scoreTag("海道", hokkaido)).toBe(3));
  it("yomi の前方一致は 3", () =>
    expect(scoreTag("ほっかい", hokkaido)).toBe(3));
  it("yomi の部分一致は 2", () =>
    expect(scoreTag("かいどう", hokkaido)).toBe(2));
  it("飛び飛び一致は 1", () => expect(scoreTag("北道", hokkaido)).toBe(1));
  it("1 文字だけ一致しても 0", () => expect(scoreTag("道", rental)).toBe(0));
  it("カタカナ入力はひらがなと同じ", () =>
    expect(scoreTag("レンタ", rental)).toBe(4));
  it("一致なしは 0", () => expect(scoreTag("沖縄", hokkaido)).toBe(0));
  it("空入力は 0", () => {
    expect(scoreTag("", hokkaido)).toBe(0);
    expect(scoreTag("  ", hokkaido)).toBe(0);
  });
});

describe("searchTags", () => {
  it("設計書の例", () => {
    for (const q of ["北海", "海道", "ほっかい", "かいどう", "北道"]) {
      expect(searchTags(q, tags).map((m) => m.tag.label)).toEqual(["北海道"]);
    }
    expect(searchTags("レンタ", tags).map((m) => m.tag.label)).toEqual([
      "レンタカー",
    ]);
  });

  it("空入力・一致なしは空配列", () => {
    expect(searchTags("", tags)).toEqual([]);
    expect(searchTags("zzz", tags)).toEqual([]);
  });

  it("点数の高い順、同点は count の多い順", () => {
    const a = { label: "東京都", yomi: "とうきょうと", count: 5 };
    const b = { label: "京都府", yomi: "きょうとふ", count: 3 };
    const c = { label: "大京都", yomi: "だいきょうと", count: 9 };
    const d = { label: "京都市", yomi: "きょうとし", count: 7 };
    const r = searchTags("京都", [a, b, c, d]);
    expect(r.map((m) => m.tag.label)).toEqual([
      "京都市",
      "京都府",
      "大京都",
      "東京都",
    ]);
    expect(r.map((m) => m.score)).toEqual([4, 4, 3, 3]);
  });
});
