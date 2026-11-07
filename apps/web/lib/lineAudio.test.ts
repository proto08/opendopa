import { describe, expect, it, vi } from "vitest";
import { type AudioLike, LineAudio } from "./lineAudio";

function setup() {
  const made: (AudioLike & {
    url: string;
    play: ReturnType<typeof vi.fn>;
    pause: ReturnType<typeof vi.fn>;
  })[] = [];
  const la = new LineAudio((url) => {
    const a = { url, play: vi.fn(async () => {}), pause: vi.fn() };
    made.push(a);
    return a;
  });
  return { la, made };
}

describe("LineAudio", () => {
  it("行が進むと前の音声を止めて、次の行の音声を始める", () => {
    const { la, made } = setup();
    la.sync("v/0.mp3", "0:0", false);
    expect(made[0].play).toHaveBeenCalledTimes(1);
    la.sync("v/1.mp3", "1:0", false);
    expect(made[0].pause).toHaveBeenCalled();
    expect(made).toHaveLength(2);
    expect(made[1].url).toBe("v/1.mp3");
    expect(made[1].play).toHaveBeenCalledTimes(1);
  });

  it("一時停止で止まり、再開で同じ音声を続きから鳴らす(作り直さない)", () => {
    const { la, made } = setup();
    la.sync("v/0.mp3", "0:0", false);
    la.sync("v/0.mp3", "0:0", true);
    expect(made[0].pause).toHaveBeenCalledTimes(1);
    la.sync("v/0.mp3", "0:0", false);
    expect(made).toHaveLength(1);
    expect(made[0].play).toHaveBeenCalledTimes(2);
  });

  it("ループで同じ URL でも、鍵が変われば頭から鳴らし直す", () => {
    const { la, made } = setup();
    la.sync("v/0.mp3", "0:0", false);
    la.sync("v/0.mp3", "0:1", false);
    expect(made).toHaveLength(2);
    expect(made[0].pause).toHaveBeenCalled();
  });

  it("URL が null(離脱・音声なし)で止まる", () => {
    const { la, made } = setup();
    la.sync("v/0.mp3", "0:0", false);
    la.sync(null, "0:0", false);
    expect(made[0].pause).toHaveBeenCalled();
    la.sync("v/0.mp3", "0:0", false); // 戻ってきたら頭から
    expect(made).toHaveLength(2);
  });

  it("自動再生が拒否されても例外にしない", async () => {
    const la = new LineAudio(() => ({
      play: () => Promise.reject(new Error("blocked")),
      pause: vi.fn(),
    }));
    expect(() => la.sync("v/0.mp3", "0:0", false)).not.toThrow();
    await Promise.resolve();
  });

  it("音声なしの動画(url が null)では Audio を作らない", () => {
    const create = vi.fn();
    new LineAudio(create).sync(null, "0:0", false);
    expect(create).not.toHaveBeenCalled();
  });
});
