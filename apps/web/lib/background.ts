// 動画の背景画像。データセット ID から、`public/bg/` の画像を引く(Issue #180)。
// 対応表はここだけに持つ。シーンJSON・DB・pipeline は変えない。

const BACKGROUNDS = {
  drone: ["accident", "flightplan"],
  home: ["akiya_reg", "akiya_sold"],
  car: ["rental_result", "rental_fleet"],
  ship: ["naiko_route", "naiko_ship"],
  train: [
    "rail_traffic1",
    "rail_traffic2",
    "rail_km",
    "rail_pl",
    "rail_income",
    "rail_bs",
  ],
} as const;

export type BackgroundName = keyof typeof BACKGROUNDS;

const BY_DATASET: ReadonlyMap<string, BackgroundName> = new Map(
  (Object.keys(BACKGROUNDS) as BackgroundName[]).flatMap((name) =>
    BACKGROUNDS[name].map((id): [string, BackgroundName] => [id, name]),
  ),
);

/** 画像の名前(`public/bg/<名前>.webp`)。対応がなければ null */
export function backgroundName(datasetId: string): BackgroundName | null {
  return BY_DATASET.get(datasetId) ?? null;
}

/** 背景画像の URL(`public/` からの絶対パス)。対応がなければ null(画像なしで描画する) */
export function backgroundSrc(datasetId: string): string | null {
  const name = backgroundName(datasetId);
  return name === null ? null : `/bg/${name}.webp`;
}

/** 全画像の名前(テスト用) */
export const BACKGROUND_NAMES = Object.keys(BACKGROUNDS) as BackgroundName[];
