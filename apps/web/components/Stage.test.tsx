import { validateScene } from "@opendopa/shared";
import accident from "@opendopa/shared/fixtures/accident-0001.json";
import mapPoints from "@opendopa/shared/fixtures/map-points.json";
import mapPolygon from "@opendopa/shared/fixtures/map-polygon.json";
import mapRoute from "@opendopa/shared/fixtures/map-route.json";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AiLabel } from "./AiLabel";
import { Comments } from "./Comments";
import { Footer } from "./Footer";
import { SourceLine } from "./SourceLine";

const fixtures = Object.entries({
  "accident-0001": accident,
  "map-points": mapPoints,
  "map-polygon": mapPolygon,
  "map-route": mapRoute,
}).map(([name, json]) => {
  const r = validateScene(json);
  if (!r.ok) throw new Error(name);
  return { name, scene: r.scene };
});

describe("必須の表示", () => {
  it.each(fixtures)("$name: AI 生成のラベルと出典が出る", ({ scene }) => {
    const html = renderToStaticMarkup(
      <>
        <AiLabel />
        <SourceLine source={scene.source} />
      </>,
    );
    expect(html).toContain("AI生成のフィクション風解説");
    expect(html).toContain(
      `出典:${scene.source.datasetName} / ${scene.source.ref}`,
    );
  });

  it("フッターは非公式の旨を常に出し、credit があるときだけクレジットを足す", () => {
    const plain = renderToStaticMarkup(<Footer />);
    expect(plain).toContain("OpenDopaは非公式のアプリです");
    expect(plain).not.toContain("VOICEVOX");
    expect(
      renderToStaticMarkup(<Footer credit="VOICEVOX:四国めたん" />),
    ).toContain("VOICEVOX:四国めたん");
  });
});

describe("Comments", () => {
  it("comments: [] では要素を出さない", () => {
    expect(
      renderToStaticMarkup(
        <Comments comments={[]} totalSec={20} playedSec={5} />,
      ),
    ).toBe("");
  });

  it("時刻が同じなら位置も同じ(一時停止中は進まない)", () => {
    const comments = [{ t: 1, text: "気をつけたい", style: "normal" as const }];
    const render = () =>
      renderToStaticMarkup(
        <Comments comments={comments} totalSec={20} playedSec={3} />,
      );
    expect(render()).toContain("気をつけたい");
    expect(render()).toBe(render());
  });

  it("yellow のコメントに data-style が付く", () => {
    const html = renderToStaticMarkup(
      <Comments
        comments={[{ t: 0, text: "a", style: "yellow" }]}
        totalSec={20}
        playedSec={1}
      />,
    );
    expect(html).toContain('data-style="yellow"');
  });
});
