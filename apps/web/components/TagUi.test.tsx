import type { Tag } from "@opendopa/shared";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { TagInfo } from "@/lib/tagFilter";
import { PoolEmpty } from "./PoolEmpty";
import { SearchButton } from "./SearchButton";
import { TagSearchSheet } from "./TagSearchSheet";
import { VideoTags } from "./VideoTags";

const catalog: TagInfo[] = [
  {
    id: "dataset:rental",
    kind: "dataset",
    label: "レンタカー",
    yomi: "れんたかー",
    count: 10,
  },
  {
    id: "region:hokkaido",
    kind: "region",
    label: "北海道",
    yomi: "ほっかいどう",
    count: 42,
  },
];
const noop = () => {};

describe("PoolEmpty(pool_empty の案内)", () => {
  it("案内と「タグを全部外す」を出す", () => {
    const html = renderToStaticMarkup(<PoolEmpty onClear={noop} />);
    expect(html).toContain("見終わりました。この条件の動画はありません。");
    expect(html).toContain("タグを全部外す");
  });
});

describe("SearchButton", () => {
  it("絞り込みなしはアイコンだけ。絞り込み中は「絞り込み中 N本」", () => {
    const off = renderToStaticMarkup(
      <SearchButton filtering={false} count={null} onOpen={noop} />,
    );
    expect(off).not.toContain("絞り込み中");
    expect(off).toContain('data-filtering="false"');
    const on = renderToStaticMarkup(
      <SearchButton filtering count={12} onOpen={noop} />,
    );
    expect(on).toContain("絞り込み中 12本");
    expect(on).toContain('data-filtering="true"');
  });
});

describe("VideoTags", () => {
  const tags: Tag[] = [
    { id: "dataset:rental", kind: "dataset", label: "レンタカー" },
    { id: "region:hokkaido", kind: "region", label: "北海道" },
  ];
  it("#つきで並べ、選択中は aria-pressed。タグがなければ何も出さない", () => {
    const html = renderToStaticMarkup(
      <VideoTags tags={tags} selected={["region:hokkaido"]} />,
    );
    expect(html).toContain("#レンタカー");
    expect(html).toContain("#北海道");
    expect(html.match(/aria-pressed="true"/g)).toHaveLength(1);
    expect(renderToStaticMarkup(<VideoTags tags={[]} selected={[]} />)).toBe(
      "",
    );
  });
});

describe("TagSearchSheet", () => {
  const render = (over: Partial<Parameters<typeof TagSearchSheet>[0]> = {}) =>
    renderToStaticMarkup(
      <TagSearchSheet
        catalog={catalog}
        failed={false}
        selected={[]}
        onClose={noop}
        {...over}
      />,
    );
  it("空入力は、データの種類と件数の多い地域を、種別/地域・#タグ名・N本で出す", () => {
    const html = render();
    expect(html).toContain("データの種類");
    expect(html).toContain("件数の多い地域");
    expect(html).toContain("種別");
    expect(html).toContain("地域");
    expect(html).toContain("42本");
  });
  it("選択済みは × で外せ、候補では選べない", () => {
    const html = render({ selected: ["region:hokkaido"] });
    expect(html).toContain("選択中のタグ");
    expect(html).toContain("#北海道 を外す");
    expect(html).toMatch(
      /<button[^>]*disabled=""[^>]*class="tagSheetRow"|class="tagSheetRow"[^>]*disabled=""/,
    );
  });
  it("入力で絞り、強調する。一致なしは案内を出す", () => {
    const hit = render({ initialQuery: "北海" });
    expect(hit).toContain("<mark>北海</mark>");
    expect(hit).not.toContain("レンタカー");
    const none = render({ initialQuery: "ぜんぜん" });
    expect(none).toContain(
      "『ぜんぜん』に合うタグはありません。都道府県名やデータの種類で探してください。",
    );
  });
  it("読み込み失敗と読み込み中の表示", () => {
    expect(render({ failed: true })).toContain("タグを読み込めませんでした");
    expect(render({ catalog: null })).toContain("読み込み中");
  });
});
