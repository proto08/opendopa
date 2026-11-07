import { afterEach, describe, expect, it, vi } from "vitest";
import {
  type AudioElementLike,
  audioBlocked,
  takeUnlockGesture,
} from "./audioChannel";
import { LineAudio } from "./lineAudio";

type FakeElement = AudioElementLike & {
  play: ReturnType<typeof vi.fn>;
  pause: ReturnType<typeof vi.fn>;
  paused: boolean;
  ended: boolean;
};

function fakeElement(): FakeElement {
  const el: FakeElement = {
    src: "",
    currentTime: 0,
    paused: true,
    ended: false,
    onended: null,
    play: vi.fn(async () => {
      el.paused = false;
    }),
    pause: vi.fn(() => {
      el.paused = true;
    }),
  };
  return el;
}

function fakeTarget() {
  const handlers = new Map<string, () => void>();
  return {
    addEventListener: vi.fn((type: string, h: () => void) => {
      handlers.set(type, h);
    }),
    removeEventListener: vi.fn((type: string) => {
      handlers.delete(type);
    }),
    fire: (type: string) => handlers.get(type)?.(),
    has: (type: string) => handlers.has(type),
  };
}

const notAllowed = () =>
  Object.assign(new Error("blocked"), { name: "NotAllowedError" });
const flush = () => new Promise((r) => setTimeout(r, 0));

afterEach(() => {
  audioBlocked.set(false);
  takeUnlockGesture();
});

describe("LineAudio", () => {
  it("1 本の要素を使い回し、行が進むと src だけ差し替えて頭から鳴らす", () => {
    const el = fakeElement();
    const la = new LineAudio({ element: el });
    la.sync("v/0.mp3", "0:0", false);
    expect(el.src).toBe("v/0.mp3");
    expect(el.play).toHaveBeenCalledTimes(1);
    la.sync("v/1.mp3", "1:0", false);
    expect(el.src).toBe("v/1.mp3");
    expect(el.play).toHaveBeenCalledTimes(2);
  });

  it("一時停止で止まり、再開で src を変えずに続きから鳴らす", () => {
    const el = fakeElement();
    const la = new LineAudio({ element: el, getOffsetSec: () => 1.5 });
    la.sync("v/0.mp3", "0:0", false);
    el.currentTime = 1.5; // 1.5 秒まで鳴っていた
    la.sync("v/0.mp3", "0:0", true);
    expect(el.pause).toHaveBeenCalledTimes(1);
    la.sync("v/0.mp3", "0:0", false);
    expect(el.currentTime).toBe(1.5);
    expect(el.play).toHaveBeenCalledTimes(2);
  });

  it("音声の位置が字幕の位置とずれていたら、字幕に合わせてから鳴らす", () => {
    const el = fakeElement();
    let offset = 0;
    const la = new LineAudio({ element: el, getOffsetSec: () => offset });
    la.sync("v/0.mp3", "0:0", true);
    offset = 3.2; // 音声が止められている間に、字幕は 3.2 秒進んだ
    la.sync("v/0.mp3", "0:0", false);
    expect(el.currentTime).toBe(3.2);
  });

  it("ループで同じ URL でも、鍵が変われば頭から鳴らし直す", () => {
    const el = fakeElement();
    const la = new LineAudio({ element: el });
    la.sync("v/0.mp3", "0:0", false);
    el.currentTime = 6;
    la.sync("v/0.mp3", "0:1", false);
    expect(el.currentTime).toBe(0);
    expect(el.play).toHaveBeenCalledTimes(2);
  });

  it("URL が null(離脱・音声なし)で止まる", () => {
    const el = fakeElement();
    const la = new LineAudio({ element: el });
    la.sync("v/0.mp3", "0:0", false);
    la.sync(null, "0:0", false);
    expect(el.pause).toHaveBeenCalled();
    expect(la.isPlaying()).toBe(false);
  });

  it("音声が最後まで鳴ったら onEnded を呼ぶ", () => {
    const el = fakeElement();
    const onEnded = vi.fn();
    const la = new LineAudio({ element: el, onEnded });
    la.sync("v/0.mp3", "0:0", false);
    el.onended?.(new Event("ended"));
    expect(onEnded).toHaveBeenCalledTimes(1);
  });

  it("鳴っている間だけ isPlaying が true", () => {
    const el = fakeElement();
    const la = new LineAudio({ element: el });
    expect(la.isPlaying()).toBe(false);
    la.sync("v/0.mp3", "0:0", false);
    expect(la.isPlaying()).toBe(true);
    la.sync("v/0.mp3", "0:0", true);
    expect(la.isPlaying()).toBe(false);
  });

  it("画面から外れた別の動画の stop は、いま鳴っている音声を止めない", () => {
    const el = fakeElement();
    const active = new LineAudio({ element: el });
    const inactive = new LineAudio({ element: el });
    active.sync("v/a.mp3", "0:0", false);
    el.pause.mockClear();
    inactive.sync(null, "0:0", false);
    inactive.stop();
    expect(el.pause).not.toHaveBeenCalled();
    expect(active.isPlaying()).toBe(true);
  });

  it("次の動画が音声を引き継ぐと、前の動画は鳴らす権利を失う", () => {
    const el = fakeElement();
    const prev = new LineAudio({ element: el });
    const next = new LineAudio({ element: el });
    prev.sync("v/a.mp3", "0:0", false);
    next.sync("v/b.mp3", "0:0", false);
    prev.stop(); // 遅れて呼ばれても、次の動画の音声を止めない
    expect(el.src).toBe("v/b.mp3");
    expect(next.isPlaying()).toBe(true);
    expect(prev.isPlaying()).toBe(false);
  });

  describe("自動再生が止められたとき", () => {
    it("例外にせず、ミュート状態にして、最初の操作を待つ", async () => {
      const el = fakeElement();
      el.play.mockRejectedValueOnce(notAllowed());
      const target = fakeTarget();
      const la = new LineAudio({ element: el, gestureTarget: target });
      expect(() => la.sync("v/0.mp3", "0:0", false)).not.toThrow();
      await flush();
      expect(audioBlocked.get()).toBe(true);
      expect(target.has("pointerdown")).toBe(true);
      expect(target.has("keydown")).toBe(true);
    });

    it("最初の操作で、字幕の位置から鳴らし直し、ミュート表示を消す", async () => {
      const el = fakeElement();
      el.play.mockRejectedValueOnce(notAllowed());
      const target = fakeTarget();
      let offset = 0;
      const la = new LineAudio({
        element: el,
        gestureTarget: target,
        getOffsetSec: () => offset,
      });
      la.sync("v/0.mp3", "0:0", false);
      await flush();
      offset = 2.4; // 無音のまま字幕が進んだ
      target.fire("pointerdown");
      await flush();
      expect(el.currentTime).toBe(2.4);
      expect(audioBlocked.get()).toBe(false);
      expect(target.has("pointerdown")).toBe(false);
      expect(takeUnlockGesture()).toBe(true); // この操作は一時停止に使わない
    });

    it("一時停止中に最初の操作があっても、鳴らさない", async () => {
      const el = fakeElement();
      el.play.mockRejectedValueOnce(notAllowed());
      const target = fakeTarget();
      const la = new LineAudio({ element: el, gestureTarget: target });
      la.sync("v/0.mp3", "0:0", false);
      await flush();
      la.sync("v/0.mp3", "0:0", true);
      el.play.mockClear();
      target.fire("keydown");
      expect(el.play).not.toHaveBeenCalled();
    });

    it("行の切り替えで読み込みが中断された(AbortError)ときは、ミュートにしない", async () => {
      const el = fakeElement();
      el.play.mockRejectedValueOnce(
        Object.assign(new Error("aborted"), { name: "AbortError" }),
      );
      const la = new LineAudio({ element: el, gestureTarget: fakeTarget() });
      la.sync("v/0.mp3", "0:0", false);
      await flush();
      expect(audioBlocked.get()).toBe(false);
    });

    it("stop でミュート表示と操作の待ちを片付ける", async () => {
      const el = fakeElement();
      el.play.mockRejectedValueOnce(notAllowed());
      const target = fakeTarget();
      const la = new LineAudio({ element: el, gestureTarget: target });
      la.sync("v/0.mp3", "0:0", false);
      await flush();
      la.stop();
      expect(audioBlocked.get()).toBe(false);
      expect(target.has("pointerdown")).toBe(false);
    });
  });
});

describe("takeUnlockGesture", () => {
  it("一度だけ true を返し、時間が過ぎると false", async () => {
    const { markUnlockGesture } = await import("./audioChannel");
    markUnlockGesture(1000);
    expect(takeUnlockGesture(1300)).toBe(true);
    expect(takeUnlockGesture(1300)).toBe(false);
    markUnlockGesture(1000);
    expect(takeUnlockGesture(2000)).toBe(false);
  });
});
