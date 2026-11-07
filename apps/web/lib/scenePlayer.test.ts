import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  bigNumberFontSizeCqw,
  COUNT_UP_SEC,
  computeSnapshot,
  countUpValue,
  formatBigNumber,
  lineIndexAt,
  ScenePlayer,
} from "./scenePlayer";

// 3 行: 0〜4 秒、4〜6 秒、6〜10 秒(合計 10 秒)
const lines = [{ durationSec: 4 }, { durationSec: 2 }, { durationSec: 4 }];

describe("ScenePlayer(fake timers)", () => {
  let player: ScenePlayer;
  beforeEach(() => {
    vi.useFakeTimers();
    // フェイクタイマーの時計(performance.now も偽物になる)で進める
    player = new ScenePlayer(lines);
    player.start();
  });
  afterEach(() => {
    player.stop();
    vi.useRealTimers();
  });

  it("累計時間で字幕の行が切り替わる", () => {
    expect(player.getSnapshot().lineIndex).toBe(0);
    vi.advanceTimersByTime(3900);
    expect(player.getSnapshot().lineIndex).toBe(0);
    vi.advanceTimersByTime(200);
    expect(player.getSnapshot().lineIndex).toBe(1);
    vi.advanceTimersByTime(2000);
    expect(player.getSnapshot().lineIndex).toBe(2);
  });

  it("最後の行のあとにループし、進行バーは 0 に戻る", () => {
    vi.advanceTimersByTime(9900);
    expect(player.getSnapshot().lineIndex).toBe(2);
    expect(player.getSnapshot().progress).toBeGreaterThan(0.9);
    vi.advanceTimersByTime(300);
    const snap = player.getSnapshot();
    expect(snap.loops).toBe(1);
    expect(snap.lineIndex).toBe(0);
    expect(snap.progress).toBeLessThan(0.1);
  });

  it("一時停止中は時計が進まず、再開で続きから進む", () => {
    vi.advanceTimersByTime(1000);
    player.pause();
    const paused = player.getSnapshot();
    expect(paused.paused).toBe(true);
    vi.advanceTimersByTime(20000);
    expect(player.getSnapshot().elapsedSec).toBeCloseTo(paused.elapsedSec, 5);
    expect(player.getSnapshot().loops).toBe(0);

    player.resume();
    vi.advanceTimersByTime(500);
    expect(player.getSnapshot().elapsedSec).toBeCloseTo(
      paused.elapsedSec + 0.5,
      1,
    );
    expect(player.getSnapshot().paused).toBe(false);
  });

  it("toggle で一時停止と再開を切り替え、切り替え回数が増える", () => {
    player.toggle();
    expect(player.getSnapshot()).toMatchObject({ paused: true, toggles: 1 });
    player.toggle();
    expect(player.getSnapshot()).toMatchObject({ paused: false, toggles: 2 });
  });

  it("購読者に更新を通知し、解除できる", () => {
    const fn = vi.fn();
    const off = player.subscribe(fn);
    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalled();
    off();
    fn.mockClear();
    vi.advanceTimersByTime(100);
    expect(fn).not.toHaveBeenCalled();
  });

  it("カウントアップは 1.2 秒で終わり、ループしても戻らない", () => {
    vi.advanceTimersByTime(600);
    expect(player.getSnapshot().countProgress).toBeCloseTo(0.5, 1);
    vi.advanceTimersByTime(700);
    expect(player.getSnapshot().countProgress).toBe(1);
    vi.advanceTimersByTime(10000); // ループを越える
    expect(player.getSnapshot().loops).toBeGreaterThanOrEqual(1);
    expect(player.getSnapshot().countProgress).toBe(1);
  });
});

describe("lineIndexAt / computeSnapshot", () => {
  const d = [4, 2, 4];
  it("境目は次の行になる", () => {
    expect(lineIndexAt(d, 0)).toBe(0);
    expect(lineIndexAt(d, 3.99)).toBe(0);
    expect(lineIndexAt(d, 4)).toBe(1);
    expect(lineIndexAt(d, 6)).toBe(2);
  });
  it("合計を超えると頭に戻る", () => {
    expect(computeSnapshot(d, 10, { paused: false, toggles: 0 })).toMatchObject(
      {
        loops: 1,
        elapsedSec: 0,
        lineIndex: 0,
        progress: 0,
      },
    );
  });
  it("合計 0 でも壊れない", () => {
    expect(
      computeSnapshot([0], 5, { paused: false, toggles: 0 }),
    ).toMatchObject({
      lineIndex: 0,
      progress: 0,
    });
  });
});

describe("カウントアップ", () => {
  it("0 から value へ 1.2 秒で到達する", () => {
    expect(COUNT_UP_SEC).toBe(1.2);
    expect(formatBigNumber(1234, true, 0)).toBe("0");
    expect(formatBigNumber(1234, true, 1)).toBe("1,234");
    const mid = countUpValue(1000, 0.5);
    expect(mid).toBeGreaterThan(500); // ease-out は前半が速い
    expect(mid).toBeLessThan(1000);
  });
  it("countUp=false のときは最初から value で固定", () => {
    expect(formatBigNumber(1234, false, 0)).toBe("1,234");
  });
  it("数でない value はそのまま出す", () => {
    expect(formatBigNumber("第1位", true, 0)).toBe("第1位");
  });
  it("小数は桁をそろえる", () => {
    expect(formatBigNumber(12.5, true, 1)).toBe("12.5");
    expect(formatBigNumber(12.5, true, 0)).toBe("0.0");
  });
});

describe("大きな数字の文字サイズ", () => {
  it.each([
    ["1", 21],
    ["1,234", 21],
    ["12,345", 17],
    ["123,456", 14],
    ["1,234,567", 12.5],
    ["12,345,678", 11.5],
    ["1,234,567,890", 11.5],
  ])("%s は %scqw", (text, size) => {
    expect(bigNumberFontSizeCqw(text)).toBe(size);
  });
  it("小数点は桁に数えない", () => {
    expect(bigNumberFontSizeCqw("123.4")).toBe(21);
  });
});

describe("ScenePlayer.reset", () => {
  it("一時停止して最初に戻す", () => {
    let t = 0;
    const tick: { cb?: () => void } = {};
    const p = new ScenePlayer([{ durationSec: 2 }, { durationSec: 2 }], {
      now: () => t,
      schedule: (f) => ((tick.cb = f), 1),
      cancel: () => {},
    });
    p.start();
    t = 200;
    tick.cb?.();
    expect(p.getSnapshot().playedSec).toBeGreaterThan(0);
    p.reset();
    const s = p.getSnapshot();
    expect(s.paused).toBe(true);
    expect(s.playedSec).toBe(0);
    expect(s.lineIndex).toBe(0);
    expect(s.progress).toBe(0);
  });
});

describe("ScenePlayer.hold / release(シートが開いている間の停止)", () => {
  function make() {
    let t = 0;
    const tick: { cb?: () => void } = {};
    const p = new ScenePlayer([{ durationSec: 4 }], {
      now: () => t,
      schedule: (f) => ((tick.cb = f), 1),
      cancel: () => {},
    });
    return { p, advance: (ms: number) => ((t += ms), tick.cb?.()) };
  }

  it("hold で止まり、release で続きから再開する(アイコンは出さない)", () => {
    const { p, advance } = make();
    p.start();
    advance(200);
    p.hold();
    const held = p.getSnapshot();
    expect(held.paused).toBe(true);
    expect(held.toggles).toBe(0);
    advance(5000);
    expect(p.getSnapshot().playedSec).toBeCloseTo(held.playedSec);
    p.release();
    expect(p.getSnapshot().paused).toBe(false);
    advance(200);
    expect(p.getSnapshot().playedSec).toBeGreaterThan(held.playedSec);
  });

  it("hold 中のタップでは再開しない", () => {
    const { p } = make();
    p.start();
    p.hold();
    p.toggle();
    expect(p.getSnapshot().paused).toBe(true);
  });

  it("利用者が止めていたら、release しても再開しない", () => {
    const { p } = make();
    p.start();
    p.pause();
    p.hold();
    p.release();
    expect(p.getSnapshot().paused).toBe(true);
  });
});
