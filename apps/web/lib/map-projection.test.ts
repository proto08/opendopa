import { describe, expect, it } from "vitest";
import japan from "./data/japan.json";
import { fitView, JAPAN_VIEW, MAP_HEIGHT, MAP_WIDTH, project, type LonLat } from "./map-projection";

describe("project", () => {
  it("日本全体の範囲で、北は上・東は右になり、画面内に入る", () => {
    const tokyo = project(139.7, 35.7, JAPAN_VIEW)!;
    const sapporo = project(141.35, 43.06, JAPAN_VIEW)!;
    const naha = project(127.68, 26.21, JAPAN_VIEW)!;
    for (const [x, y] of [tokyo, sapporo, naha]) {
      expect(x).toBeGreaterThan(0);
      expect(x).toBeLessThan(MAP_WIDTH);
      expect(y).toBeGreaterThan(0);
      expect(y).toBeLessThan(MAP_HEIGHT);
    }
    expect(sapporo[1]).toBeLessThan(tokyo[1]);
    expect(naha[0]).toBeLessThan(tokyo[0]);
    expect(naha[1]).toBeGreaterThan(tokyo[1]);
  });

  it("範囲の中心は画面の中心に来る", () => {
    const view = fitView([
      [130, 33],
      [132, 35],
    ]);
    const [x, y] = project(131, 34, view)!;
    expect(x).toBeCloseTo(MAP_WIDTH / 2, 5);
    expect(y).toBeCloseTo(MAP_HEIGHT / 2, 5);
  });

  it("日本の外の座標でも例外にならず、有限でない値は null", () => {
    const p = project(-74, 40.7, JAPAN_VIEW)!;
    expect(Number.isFinite(p[0]) && Number.isFinite(p[1])).toBe(true);
    expect(project(Number.NaN, 35, JAPAN_VIEW)).toBeNull();
    expect(fitView([[Number.NaN, Number.NaN]])).toEqual(JAPAN_VIEW);
    expect(fitView([])).toEqual(JAPAN_VIEW);
  });
});

describe("fitView", () => {
  it("小さな範囲は日本全体より拡大され、対象は画面内に収まる", () => {
    const pts: LonLat[] = [
      [131.2, 34.4],
      [137.0, 37.0],
    ];
    const view = fitView(pts);
    expect(view.width).toBeLessThan(JAPAN_VIEW.width);
    for (const [lon, lat] of pts) {
      const [x, y] = project(lon, lat, view)!;
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(MAP_WIDTH);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(MAP_HEIGHT);
    }
  });

  it("縦長の範囲でも縦横比は viewBox と同じで、はみ出さない", () => {
    const pts: LonLat[] = [
      [135, 26],
      [135.5, 45],
    ];
    const view = fitView(pts);
    expect(view.width / view.height).toBeCloseTo(MAP_WIDTH / MAP_HEIGHT, 5);
    for (const [lon, lat] of pts) {
      const [x, y] = project(lon, lat, view)!;
      expect(x).toBeGreaterThan(0);
      expect(x).toBeLessThan(MAP_WIDTH);
      expect(y).toBeGreaterThan(0);
      expect(y).toBeLessThan(MAP_HEIGHT);
    }
  });

  it("1 点でも拡大しすぎない(最小の幅がある)", () => {
    const one = fitView([[139.7, 35.7]]);
    expect(one.width).toBeGreaterThan(0);
    expect(one.height).toBeGreaterThan(0);
  });
});

describe("日本の輪郭データ", () => {
  it("北海道から沖縄までを含み、座標は日本付近にある", () => {
    const pts = (japan as unknown as LonLat[][]).flat();
    const lats = pts.map((p) => p[1]);
    expect(Math.min(...lats)).toBeLessThan(27);
    expect(Math.max(...lats)).toBeGreaterThan(45);
    for (const [lon, lat] of pts) {
      expect(lon).toBeGreaterThan(122);
      expect(lon).toBeLessThan(155);
      expect(lat).toBeGreaterThan(23);
      expect(lat).toBeLessThan(46);
    }
  });
});
