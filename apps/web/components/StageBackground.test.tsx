import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { StageBackground } from "./StageBackground";

describe("StageBackground", () => {
  it.each([
    ["accident", "/bg/drone.webp"],
    ["akiya_reg", "/bg/home.webp"],
    ["rental_result", "/bg/car.webp"],
    ["naiko_ship", "/bg/ship.webp"],
    ["rail_km", "/bg/train.webp"],
  ])("%s は %s を敷き、暗いレイヤーを重ねる", (datasetId, src) => {
    const html = renderToStaticMarkup(
      <StageBackground datasetId={datasetId} />,
    );
    expect(html).toContain(`src="${src}"`);
    expect(html).toContain('aria-hidden="true"');
    expect(html).toContain('alt=""');
    expect(html).toContain("bgShade");
  });

  it("対応のないデータセットは何も出さない(従来の描画)", () => {
    expect(renderToStaticMarkup(<StageBackground datasetId="unknown" />)).toBe(
      "",
    );
  });
});
