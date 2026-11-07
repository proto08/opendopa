import { afterEach, describe, expect, it, vi } from "vitest";
import { takeUnlockGesture } from "./audioChannel";
import { Bgm, type BgmElementLike } from "./bgm";

function setup(playImpl?: () => Promise<void>) {
  const el = {
    src: "",
    loop: false,
    volume: 1,
    muted: false,
    play: vi.fn<() => Promise<void>>(playImpl ?? (async () => {})),
    pause: vi.fn<() => void>(),
  };
  const handlers = new Map<string, () => void>();
  const target = {
    addEventListener: vi.fn((t: string, h: () => void) => handlers.set(t, h)),
    removeEventListener: vi.fn((t: string) => handlers.delete(t)),
  };
  const bgm = new Bgm(el as BgmElementLike, target, "https://x/a.mp3", 0.2);
  return { el, handlers, bgm };
}

afterEach(() => takeUnlockGesture());

describe("Bgm", () => {
  it("ループと音量を設定して鳴らす", () => {
    const { el, bgm } = setup();
    bgm.start();
    expect(el).toMatchObject({
      src: "https://x/a.mp3",
      loop: true,
      volume: 0.2,
    });
    expect(el.play).toHaveBeenCalledTimes(1);
  });

  it("自動再生が止められたら、最初の操作で鳴らし直し、その操作を一時停止にしない", async () => {
    const { el, handlers, bgm } = setup(async () => {
      throw new DOMException("blocked", "NotAllowedError");
    });
    bgm.start();
    await Promise.resolve();
    await Promise.resolve();
    expect(handlers.has("pointerdown")).toBe(true);
    handlers.get("pointerdown")?.();
    expect(el.play).toHaveBeenCalledTimes(2);
    expect(handlers.size).toBe(0);
    expect(takeUnlockGesture()).toBe(true);
  });

  it("ミュートで止めて、解除で鳴らし直す。stop は待機も解く", () => {
    const { el, bgm } = setup();
    bgm.start();
    bgm.setMuted(true);
    expect(el.pause).toHaveBeenCalled();
    bgm.start();
    expect(el.play).toHaveBeenCalledTimes(1);
    bgm.setMuted(false);
    expect(el.play).toHaveBeenCalledTimes(2);
    bgm.stop();
    expect(el.pause).toHaveBeenCalledTimes(2);
  });
});
