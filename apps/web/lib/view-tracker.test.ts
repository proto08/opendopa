import { describe, expect, it } from "vitest";
import { ViewTracker, type ViewPayload } from "./view-tracker";

function setup() {
  let t = 0;
  let n = 0;
  const sent: { payload: ViewPayload; beacon: boolean }[] = [];
  const tracker = new ViewTracker({
    now: () => t,
    newViewId: () => `view-${++n}`,
    send: (payload, beacon) => sent.push({ payload, beacon }),
  });
  return { tracker, sent, advance: (ms: number) => (t += ms) };
}

describe("ViewTracker", () => {
  it("再生中に離れる → 再生した秒数を送る", () => {
    const { tracker, sent, advance } = setup();
    tracker.show("a");
    advance(14_300);
    tracker.hide();
    expect(sent).toEqual([{ payload: { viewId: "view-1", videoId: "a", watchedSec: 14.3 }, beacon: false }]);
  });

  it("一時停止の時間は含めない", () => {
    const { tracker, sent, advance } = setup();
    tracker.show("a");
    advance(3000);
    tracker.setPaused(true);
    advance(10_000);
    tracker.setPaused(false);
    advance(2000);
    tracker.hide();
    expect(sent[0].payload.watchedSec).toBe(5);
  });

  it("一時停止したまま離れても、その時点までの秒数を送る", () => {
    const { tracker, sent, advance } = setup();
    tracker.show("a");
    advance(4000);
    tracker.setPaused(true);
    advance(60_000);
    tracker.hide();
    expect(sent[0].payload.watchedSec).toBe(4);
  });

  it("一時停止中に表示された動画は、再開してから数える", () => {
    const { tracker, sent, advance } = setup();
    tracker.setPaused(true);
    tracker.show("a");
    advance(5000);
    tracker.setPaused(false);
    advance(1500);
    tracker.hide();
    expect(sent[0].payload.watchedSec).toBe(1.5);
  });

  it("同じ視聴で 2 回送らない", () => {
    const { tracker, sent, advance } = setup();
    tracker.show("a");
    advance(1000);
    tracker.suspend(); // visibilitychange
    tracker.suspend(); // pagehide
    tracker.hide();
    expect(sent).toHaveLength(1);
    expect(sent[0].beacon).toBe(true);
  });

  it("viewId は視聴ごとに違う(同じ動画を戻って見ても、タブから戻っても)", () => {
    const { tracker, sent, advance } = setup();
    tracker.show("a");
    advance(1000);
    tracker.hide();
    tracker.show("a");
    advance(1000);
    tracker.suspend();
    tracker.resume();
    advance(2000);
    tracker.hide();
    const ids = sent.map((s) => s.payload.viewId);
    expect(new Set(ids).size).toBe(3);
    expect(sent.map((s) => s.payload.watchedSec)).toEqual([1, 1, 2]);
  });

  it("別の動画を表示すると、前の動画の視聴を先に送る", () => {
    const { tracker, sent, advance } = setup();
    tracker.show("a");
    advance(2000);
    tracker.show("b");
    advance(1000);
    tracker.hide();
    expect(sent.map((s) => [s.payload.videoId, s.payload.watchedSec])).toEqual([
      ["a", 2],
      ["b", 1],
    ]);
  });

  it("表示されていない間は何も送らない", () => {
    const { tracker, sent } = setup();
    tracker.hide();
    tracker.suspend();
    tracker.resume();
    expect(sent).toHaveLength(0);
  });
});
