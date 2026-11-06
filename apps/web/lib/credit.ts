// フッターに出す音声のクレジット(設計書 §8.8)。VOICEVOX を使うときだけ出す。

/** 既定の声は VOICEVOX_SPEAKER=3(ずんだもん)。変えたら TTS_CREDIT も合わせる */
const DEFAULT_CREDIT = "VOICEVOX:ずんだもん";

export function ttsCredit(
  env: Record<string, string | undefined> = process.env,
): string | undefined {
  if (env.TTS_PROVIDER !== "voicevox") return undefined;
  return env.TTS_CREDIT?.trim() || DEFAULT_CREDIT;
}
