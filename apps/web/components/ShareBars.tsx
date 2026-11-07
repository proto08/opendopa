import type { Taste } from "@/lib/types";

/** カテゴリ(クラスタ)別の割合の横棒グラフ。多い順 */
export function ShareBars({ shares }: { shares: Taste["shares"] }) {
  const sorted = [...shares].sort((a, b) => b.pct - a.pct);
  return (
    <ul className="shareBars" aria-label="カテゴリ別の割合">
      {sorted.map((s) => (
        <li key={s.clusterId} className="shareRow" data-pct={s.pct}>
          <span className="shareName">{s.name}</span>
          <span className="shareTrack">
            <span className="shareFill" style={{ width: `${s.pct}%`, background: s.color }} />
          </span>
          <span className="sharePct">{s.pct}%</span>
        </li>
      ))}
    </ul>
  );
}
