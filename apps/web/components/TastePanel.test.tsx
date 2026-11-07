import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { FeedMap } from "@/lib/feedTypes";
import { TasteStore } from "@/lib/taste-store";
import type { Taste } from "@/lib/types";
import { TastePanel } from "./TastePanel";

const map: FeedMap = {
  points: [
    { videoId: "a", datasetId: "x", x: 0.1, y: 0.2, clusterId: 1 },
    { videoId: "b", datasetId: "x", x: 0.8, y: 0.6, clusterId: 2 },
    { videoId: "c", datasetId: "x", x: 0.5, y: 0.5, clusterId: 2 },
  ],
  clusters: [
    { id: 1, name: "鉄道の収支", color: "#ff0000", cx: 0.1, cy: 0.2 },
    { id: 2, name: "空き家", color: "#00ff00", cx: 0.8, cy: 0.6 },
  ],
};

const entry = (i: number) => ({
  videoId: `v${i}`,
  headline: `見出し${i}`,
  reasonLabel: "好みに近い",
  ratio: 0.5,
  liked: i === 0,
});

const taste: Taste = {
  x: 0.3,
  y: 0.4,
  shares: [
    { clusterId: 1, name: "鉄道の収支", color: "#ff0000", pct: 41 },
    { clusterId: 2, name: "空き家", color: "#00ff00", pct: 59 },
  ],
  summary: "あなたは「空き家」を最後まで見る人です",
  eventCount: 7,
  log: Array.from({ length: 6 }, (_, i) => entry(i)),
};

function render(current: string | null, viewed: string[]) {
  const store = new TasteStore();
  store.setMap(map);
  store.applyTaste(taste);
  viewed.forEach((v) => store.markViewed(v));
  store.setCurrent(current);
  return renderToStaticMarkup(<TastePanel state={store.getSnapshot()} />);
}

describe("TastePanel", () => {
  it("見た動画は濃く、見ていない動画は薄い", () => {
    const html = render(null, ["a"]);
    expect(html).toMatch(
      /data-video-id="a" data-viewed="true"[^>]*opacity="1"/,
    );
    expect(html).toMatch(
      /data-video-id="b" data-viewed="false"[^>]*opacity="0.3"/,
    );
  });

  it("再生中の動画だけ点線の輪で囲む", () => {
    const html = render("b", []);
    expect(html.match(/data-current-ring=/g)).toHaveLength(1);
    expect(html).toContain('data-current-ring="b"');
    expect(render(null, [])).not.toContain("data-current-ring");
  });

  it("いまの好みは黄色の点として、座標どおりの位置に出る", () => {
    const html = render(null, []);
    // x=0.3, y=0.4 → 6 + 0.3*88 = 32.4, 6 + 0.4*88 = 41.2
    expect(html).toContain("data-taste-dot");
    expect(html).toContain("translate(32.4px, 41.2px)");
  });

  it("割合は合計 100% で、要約が表示される", () => {
    const html = render(null, []);
    const pcts = [...html.matchAll(/class="sharePct">(\d+)%/g)].map((m) =>
      Number(m[1]),
    );
    expect(pcts.reduce((a, b) => a + b, 0)).toBe(100);
    expect(html).toContain("あなたは「空き家」を最後まで見る人です");
  });

  it("最近の視聴は 6 件を超えない", () => {
    const many: Taste = {
      ...taste,
      log: Array.from({ length: 9 }, (_, i) => entry(i)),
    };
    const store = new TasteStore();
    store.applyTaste(many);
    const html = renderToStaticMarkup(
      <TastePanel state={store.getSnapshot()} />,
    );
    expect(html.match(/class="viewLogItem"/g)).toHaveLength(6);
    expect(html).toContain("見出し0");
    expect(html).toContain("視聴 50%");
    expect(html).toContain("好みに近い");
    expect(html.match(/viewLogLike/g)).toHaveLength(1);
  });

  it("taste がまだないときは読み込み中", () => {
    const html = renderToStaticMarkup(
      <TastePanel state={new TasteStore().getSnapshot()} />,
    );
    expect(html).toContain("読み込み中");
  });
});
