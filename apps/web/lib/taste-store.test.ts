import { describe, expect, it } from "vitest";
import { toSvg } from "./taste-map";
import { TasteStore, TRAIL_MAX } from "./taste-store";
import type { Taste } from "./types";

const taste = (x: number, y: number, videoIds: string[] = []): Taste => ({
  x,
  y,
  shares: [],
  summary: "",
  eventCount: videoIds.length,
  log: videoIds.map((videoId) => ({
    videoId,
    headline: "",
    reasonLabel: "",
    ratio: 1,
    liked: false,
  })),
});

describe("TasteStore", () => {
  it("taste を受け取ると、軌跡に現在地が足され、記録の動画が見た扱いになる", () => {
    const s = new TasteStore();
    s.applyTaste(taste(0.1, 0.2, ["a"]));
    s.applyTaste(taste(0.3, 0.4, ["b", "a"]));
    const st = s.getSnapshot();
    expect(st.trail).toEqual([
      { x: 0.1, y: 0.2 },
      { x: 0.3, y: 0.4 },
    ]);
    expect([...st.viewed].sort()).toEqual(["a", "b"]);
  });

  it("位置が変わらなければ軌跡を増やさず、軌跡は上限を超えない", () => {
    const s = new TasteStore();
    s.applyTaste(taste(0.5, 0.5));
    s.applyTaste(taste(0.5, 0.5));
    expect(s.getSnapshot().trail).toHaveLength(1);
    for (let i = 0; i < TRAIL_MAX + 10; i++) s.applyTaste(taste(i / 100, 0));
    expect(s.getSnapshot().trail).toHaveLength(TRAIL_MAX);
  });

  it("シートの開閉と購読", () => {
    const s = new TasteStore();
    let calls = 0;
    s.subscribe(() => calls++);
    s.openSheet();
    s.openSheet();
    expect(s.getSnapshot().sheetOpen).toBe(true);
    s.closeSheet();
    expect(s.getSnapshot().sheetOpen).toBe(false);
    expect(calls).toBe(2);
  });
});

describe("toSvg", () => {
  it("0〜1 を余白つきの SVG 座標にし、範囲外は丸める", () => {
    expect(toSvg(0, 0)).toEqual([6, 6]);
    expect(toSvg(1, 1)).toEqual([94, 94]);
    expect(toSvg(0.5, 0.5)).toEqual([50, 50]);
    expect(toSvg(-3, 9)).toEqual([6, 94]);
    expect(toSvg(NaN, 0.5)).toEqual([6, 50]);
  });
});
