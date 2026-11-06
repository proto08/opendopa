import { describe, expect, it } from "vitest";
import type { FlowComment } from "@opendopa/shared";
import {
  LANE_COUNT,
  MAX_DURATION_SEC,
  MIN_DURATION_SEC,
  activeComments,
  assignLane,
  commentDuration,
} from "./comments";

const c = (t: number, text = "あ", style: FlowComment["style"] = "normal"): FlowComment => ({
  t,
  text,
  style,
});

describe("assignLane", () => {
  it("空きがあれば最初の空きレーンを返す", () => {
    expect(assignLane([10, 0, 0, 0, 0, 0, 0], 5)).toBe(1);
  });
  it("空く時刻ちょうどは空きとみなす", () => {
    expect(assignLane([5, 9, 9, 9, 9, 9, 9], 5)).toBe(0);
  });
  it("全レーンが使用中なら null", () => {
    expect(assignLane(Array(LANE_COUNT).fill(10), 5)).toBeNull();
  });
});

describe("commentDuration", () => {
  it("6〜8.5 秒に収まり、同じ入力なら同じ値", () => {
    for (let i = 0; i < 50; i++) {
      const d = commentDuration(c(i * 0.7, `コメント${i}`));
      expect(d).toBeGreaterThanOrEqual(MIN_DURATION_SEC);
      expect(d).toBeLessThanOrEqual(MAX_DURATION_SEC);
    }
    expect(commentDuration(c(3.2, "気をつけたい"))).toBe(commentDuration(c(3.2, "気をつけたい")));
  });
});

describe("activeComments", () => {
  it("comments が空なら何も出さない", () => {
    expect(activeComments([], 20, 5)).toEqual([]);
  });

  it("t の前は出ず、t 以降に出て、流れ終わると消える", () => {
    const list = [c(3)];
    expect(activeComments(list, 20, 2.9)).toEqual([]);
    const [a] = activeComments(list, 20, 3);
    expect(a.progress).toBe(0);
    expect(activeComments(list, 20, 3 + MAX_DURATION_SEC + 0.01)).toEqual([]);
  });

  it("同じ時刻に複数あっても別のレーンになり、重ならない", () => {
    const list = [c(1, "a"), c(1, "b"), c(1, "c")];
    const lanes = activeComments(list, 20, 2).map((a) => a.lane);
    expect(new Set(lanes).size).toBe(3);
  });

  it("全レーンが使用中なら、その回は出さない(あとで出し直さない)", () => {
    const list = Array.from({ length: LANE_COUNT + 2 }, (_, i) => c(1, `x${i}`));
    expect(activeComments(list, 20, 1.5)).toHaveLength(LANE_COUNT);
    // 全部流れ終わったあとも、出せなかった分は出ない
    expect(activeComments(list, 20, 1 + MAX_DURATION_SEC + 0.1)).toEqual([]);
  });

  it("ループしても同じ時刻に出る", () => {
    const list = [c(3)];
    expect(activeComments(list, 20, 23.5)).toHaveLength(1);
    expect(activeComments(list, 20, 43.5)).toHaveLength(1);
  });

  it("時刻が止まっていれば(一時停止)、位置は進まない", () => {
    const list = [c(3), c(4, "い", "yellow")];
    expect(activeComments(list, 20, 6)).toEqual(activeComments(list, 20, 6));
  });

  it("再生秒を進めても、画面にいるコメントのレーンは変わらない", () => {
    // 流れる時間が長く、レーンの占有が連鎖する密なコメント列
    const list = Array.from({ length: 30 }, (_, i) => c(i * 0.6, `コメント${i}`));
    const laneOf = new Map<string, number>();
    for (let t = 0; t <= 90; t += 0.1) {
      for (const a of activeComments(list, 20, t)) {
        const prev = laneOf.get(a.key);
        if (prev !== undefined) expect(a.lane).toBe(prev);
        laneOf.set(a.key, a.lane);
      }
    }
    expect(laneOf.size).toBeGreaterThan(0);
  });

  it("再生秒が進むと位置が進む", () => {
    const list = [c(3)];
    const a = activeComments(list, 20, 5)[0].progress;
    const b = activeComments(list, 20, 6)[0].progress;
    expect(b).toBeGreaterThan(a);
  });

  it("yellow のスタイルを引き継ぐ", () => {
    expect(activeComments([c(0, "a", "yellow")], 20, 1)[0].style).toBe("yellow");
  });
});
