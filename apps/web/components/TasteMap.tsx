import type { FeedMap } from "@/lib/feedTypes";
import { TASTE_MAP_SIZE, toSvg } from "@/lib/taste-map";

const FALLBACK_COLOR = "#9db0c9";

/** 全動画を並べた散布図。見た動画は濃く、再生中は点線の輪、いまの好みは黄色の大きな点 */
export function TasteMap({
  map,
  current,
  viewed,
  trail,
}: {
  map: FeedMap | null;
  current: string | null;
  viewed: ReadonlySet<string>;
  trail: readonly { x: number; y: number }[];
}) {
  const colors = new Map((map?.clusters ?? []).map((c) => [c.id, c.color]));
  const points = map?.points ?? [];
  const now = trail[trail.length - 1];
  const [dx, dy] = now ? toSvg(now.x, now.y) : [0, 0];
  const path = trail.map((t) => toSvg(t.x, t.y).join(",")).join(" ");
  const cur =
    current === null ? undefined : points.find((p) => p.videoId === current);

  return (
    <svg
      className="tasteMap"
      viewBox={`0 0 ${TASTE_MAP_SIZE} ${TASTE_MAP_SIZE}`}
      role="img"
      aria-label="動画の地図と、いまの好みの位置"
    >
      <rect
        className="tasteMapBg"
        width={TASTE_MAP_SIZE}
        height={TASTE_MAP_SIZE}
      />
      {[25, 50, 75].map((v) => (
        <g key={v} className="tasteMapGrid">
          <line x1={v} y1={0} x2={v} y2={TASTE_MAP_SIZE} />
          <line x1={0} y1={v} x2={TASTE_MAP_SIZE} y2={v} />
        </g>
      ))}
      {points.map((p) => {
        const [x, y] = toSvg(p.x, p.y);
        const seen = viewed.has(p.videoId);
        return (
          <circle
            key={p.videoId}
            className="tasteMapPoint"
            data-video-id={p.videoId}
            data-viewed={seen}
            cx={x}
            cy={y}
            r={1.5}
            fill={
              (p.clusterId !== null && colors.get(p.clusterId)) ||
              FALLBACK_COLOR
            }
            opacity={seen ? 1 : 0.3}
          />
        );
      })}
      {cur ? (
        <circle
          className="tasteMapCurrent"
          data-current-ring={cur.videoId}
          cx={toSvg(cur.x, cur.y)[0]}
          cy={toSvg(cur.x, cur.y)[1]}
          r={3.4}
        />
      ) : null}
      {trail.length > 1 ? (
        <polyline className="tasteMapTrail" points={path} />
      ) : null}
      {now ? (
        <g
          className="tasteMapTaste"
          data-taste-dot
          style={{ transform: `translate(${dx}px, ${dy}px)` }}
        >
          <circle r={3.6} />
        </g>
      ) : null}
    </svg>
  );
}
