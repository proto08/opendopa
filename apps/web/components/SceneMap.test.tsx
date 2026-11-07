import { validateScene } from "@opendopa/shared";
import mapPoints from "@opendopa/shared/fixtures/map-points.json";
import mapPolygon from "@opendopa/shared/fixtures/map-polygon.json";
import mapRoute from "@opendopa/shared/fixtures/map-route.json";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SceneMap } from "./SceneMap";

const scene = (json: unknown) => {
  const r = validateScene(json);
  if (!r.ok) throw new Error("fixture");
  return r.scene;
};

describe("SceneMap", () => {
  it("map: null では何も出さない", () => {
    expect(renderToStaticMarkup(<SceneMap map={null} />)).toBe("");
  });

  it("points: 点と地名が出る", () => {
    const html = renderToStaticMarkup(<SceneMap map={scene(mapPoints).map} />);
    expect(html).toContain('data-map-type="points"');
    expect(html).toContain("mapOutline");
    expect(html).toContain("mapDot");
    expect(html).toContain("山梨県");
  });

  it("polygon: 塗りつぶしが出る", () => {
    const html = renderToStaticMarkup(<SceneMap map={scene(mapPolygon).map} />);
    expect(html).toContain('data-map-type="polygon"');
    expect(html).toContain("mapArea");
  });

  it("route: 弧と両端の地名が出る", () => {
    const s = scene(mapRoute);
    const html = renderToStaticMarkup(<SceneMap map={s.map} />);
    expect(html).toContain('data-map-type="route"');
    expect(html).toContain("mapRoute");
    if (s.map?.type !== "route") throw new Error("fixture");
    expect(html).toContain(s.map.from.name);
    expect(html).toContain(s.map.to.name);
  });

  it("日本の外の座標や不正な値が来てもエラーにならない", () => {
    const html = renderToStaticMarkup(
      <SceneMap
        map={{
          type: "points",
          points: [
            { name: "ニューヨーク", lat: 40.7, lon: -74 },
            { name: "不正", lat: Number.NaN, lon: 0 },
          ],
        }}
      />,
    );
    expect(html).toContain("ニューヨーク");
    expect(html).not.toContain("NaN");
  });
});
