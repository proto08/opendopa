// BGM の設定(ADR・docs/decisions/2026-11-07-bgm-feed-wide-loop.md)。環境変数から読む。

export type BgmConfig = {
  /** BGM の URL */
  url: string;
  /** フッターに出すクレジット(音源の利用規約が求める表記) */
  credit: string;
  /** 0〜1。読み上げが聞き取れるよう、既定は小さめ */
  volume: number;
};

/** 読み上げ(音量 1.0)の邪魔にならない既定の音量 */
export const DEFAULT_BGM_VOLUME = 0.15;

/**
 * `BGM_FILE`(`MEDIA_BASE_URL` からの相対パス、または http(s) の URL)と
 * `BGM_CREDIT` の両方があるときだけ BGM を使う。
 * クレジットのない音源は、ライセンスを記録していないものとして鳴らさない。
 */
export function bgmConfig(
  env: Record<string, string | undefined> = process.env,
): BgmConfig | undefined {
  const file = env.BGM_FILE?.trim();
  const credit = env.BGM_CREDIT?.trim();
  if (!file || !credit) return undefined;
  const base = (env.MEDIA_BASE_URL ?? "").trim().replace(/\/+$/, "");
  const url = /^https?:\/\//.test(file)
    ? file
    : base
      ? `${base}/${file.replace(/^\/+/, "")}`
      : undefined;
  if (!url) return undefined;
  const parsed = Number(env.BGM_VOLUME);
  const volume =
    env.BGM_VOLUME?.trim() && Number.isFinite(parsed)
      ? Math.min(1, Math.max(0, parsed))
      : DEFAULT_BGM_VOLUME;
  return { url, credit, volume };
}
