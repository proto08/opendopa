import type { TasteState } from "@/lib/taste-store";
import { ShareBars } from "./ShareBars";
import { SummaryBand } from "./SummaryBand";
import { TasteMap } from "./TasteMap";
import { ViewLog } from "./ViewLog";

/** 「あなたの好み」パネル(地図・割合・要約・最近の視聴)。PC では右、スマホではシートの中身 */
export function TastePanel({ state }: { state: TasteState }) {
  const { taste, map, currentVideoId, viewed, trail } = state;
  return (
    <section className="tastePanel" aria-label="あなたの好み">
      <h2 className="tasteTitle">あなたの好み</h2>
      <TasteMap map={map} current={currentVideoId} viewed={viewed} trail={trail} />
      {taste ? (
        <>
          <ShareBars shares={taste.shares} />
          <SummaryBand summary={taste.summary} />
          <h3 className="tasteSub">最近の視聴</h3>
          <ViewLog log={taste.log} />
        </>
      ) : (
        <p className="viewLogEmpty" role="status">
          読み込み中…
        </p>
      )}
    </section>
  );
}
