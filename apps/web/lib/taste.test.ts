import { describe, expect, it } from "vitest";
import type { ClusterRow } from "./queries/clusters";
import type { LogRow } from "./queries/log";
import { buildTaste, tasteSummary } from "./taste";

const clusters: ClusterRow[] = [
  { id: 1, name: "ドローン", color: "#FF0000", cx: 0.1, cy: 0.2 },
  { id: 2, name: "鉄道", color: "#00FF00", cx: 0.5, cy: 0.6 },
];

const logRow = (n: number): LogRow => ({
  videoId: `v${n}`,
  headline: `見出し${n}`,
  reason: "near",
  ratio: 0.5,
  liked: n % 2 === 0,
});

describe("tasteSummary", () => {
  it("視聴が 0 件なら、好みはわからない", () => {
    expect(tasteSummary(0, [{ name: "A", pct: 100 }])).toBe("まだ見ていないので、好みはわかりません");
  });
  it("最大の割合が 40% 以上なら、そのクラスタ名を使う", () => {
    expect(
      tasteSummary(3, [
        { name: "A", pct: 30 },
        { name: "B", pct: 40 },
        { name: "C", pct: 30 },
      ]),
    ).toBe("あなたは「B」を最後まで見る人です");
  });
  it("それ以外は、まだ決まっていない", () => {
    expect(
      tasteSummary(3, [
        { name: "A", pct: 39 },
        { name: "B", pct: 31 },
        { name: "C", pct: 30 },
      ]),
    ).toBe("好みはまだ決まっていません。いろいろ見ています");
    expect(tasteSummary(3, [])).toBe("好みはまだ決まっていません。いろいろ見ています");
  });
});

describe("buildTaste", () => {
  const recsys = {
    x: 0.3,
    y: 0.7,
    shares: [
      { clusterId: 1, pct: 60 },
      { clusterId: 2, pct: 40 },
    ],
  };

  it("recsys の値に名前・色・要約・件数を足す", () => {
    const t = buildTaste(recsys, clusters, 4, []);
    expect(t.x).toBe(0.3);
    expect(t.y).toBe(0.7);
    expect(t.shares[0]).toEqual({ clusterId: 1, name: "ドローン", color: "#FF0000", pct: 60 });
    expect(t.summary).toBe("あなたは「ドローン」を最後まで見る人です");
    expect(t.eventCount).toBe(4);
  });

  it("log は渡された順(新しい順)で、最大 6 件。reasonLabel を付ける", () => {
    const t = buildTaste(recsys, clusters, 8, [1, 2, 3, 4, 5, 6, 7, 8].map(logRow));
    expect(t.log.map((l) => l.videoId)).toEqual(["v1", "v2", "v3", "v4", "v5", "v6"]);
    expect(t.log[0]).toEqual({
      videoId: "v1",
      headline: "見出し1",
      reasonLabel: "好みに近い",
      ratio: 0.5,
      liked: false,
    });
  });
});
