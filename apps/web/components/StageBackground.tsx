import { backgroundSrc } from "@/lib/background";

/**
 * ステージの背景画像(データセットごと。対応は `lib/background.ts`)。
 * 画像の上に、暗くするレイヤー(上と下を濃く)を重ねる。対応がなければ何も出さない。
 */
export function StageBackground({ datasetId }: { datasetId: string }) {
  const src = backgroundSrc(datasetId);
  if (src === null) return null;
  return (
    <div className="bg" aria-hidden="true">
      {/* biome-ignore lint/performance/noImgElement: 同梱の小さな WebP をそのまま敷く */}
      <img
        className="bgImage"
        src={src}
        alt=""
        decoding="async"
        draggable={false}
      />
      <div className="bgShade" />
    </div>
  );
}
