import { describe, expect, it } from "vitest";
import { bgmConfig, DEFAULT_BGM_VOLUME } from "./bgmConfig";

describe("bgmConfig", () => {
  it("BGM_FILE か BGM_CREDIT がなければ使わない", () => {
    expect(bgmConfig({})).toBeUndefined();
    expect(bgmConfig({ BGM_FILE: "bgm/a.mp3" })).toBeUndefined();
    expect(bgmConfig({ BGM_CREDIT: "BGM:x" })).toBeUndefined();
  });

  it("相対パスは MEDIA_BASE_URL につなぐ", () => {
    expect(
      bgmConfig({
        BGM_FILE: "/bgm/a.mp3",
        BGM_CREDIT: "BGM:x",
        MEDIA_BASE_URL: "https://cdn.example/media/",
      }),
    ).toEqual({
      url: "https://cdn.example/media/bgm/a.mp3",
      credit: "BGM:x",
      volume: DEFAULT_BGM_VOLUME,
    });
    expect(bgmConfig({ BGM_FILE: "a.mp3", BGM_CREDIT: "x" })).toBeUndefined();
  });

  it("URL はそのまま使い、音量は 0〜1 に収める", () => {
    const c = bgmConfig({
      BGM_FILE: "https://x.example/a.mp3",
      BGM_CREDIT: "x",
      BGM_VOLUME: "3",
    });
    expect(c?.url).toBe("https://x.example/a.mp3");
    expect(c?.volume).toBe(1);
    expect(
      bgmConfig({ BGM_FILE: "https://x/a", BGM_CREDIT: "x", BGM_VOLUME: "abc" })
        ?.volume,
    ).toBe(DEFAULT_BGM_VOLUME);
  });
});
