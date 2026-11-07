import { describe, expect, it } from "vitest";
import { ttsCredit } from "./credit";

describe("ttsCredit", () => {
  it("none・未設定ではクレジットを出さない", () => {
    expect(ttsCredit({})).toBeUndefined();
    expect(
      ttsCredit({ TTS_PROVIDER: "none", TTS_CREDIT: "VOICEVOX:x" }),
    ).toBeUndefined();
  });

  it("voicevox では TTS_CREDIT、なければ既定の声のクレジットを出す", () => {
    expect(
      ttsCredit({
        TTS_PROVIDER: "voicevox",
        TTS_CREDIT: "VOICEVOX:四国めたん",
      }),
    ).toBe("VOICEVOX:四国めたん");
    expect(ttsCredit({ TTS_PROVIDER: "voicevox" })).toBe("VOICEVOX:ずんだもん");
  });
});
