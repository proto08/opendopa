import type { Scene } from "@opendopa/shared";
import japan from "@/lib/data/japan.json";
import {
  fitView,
  type LonLat,
  MAP_HEIGHT,
  MAP_WIDTH,
  project,
  type View,
} from "@/lib/map-projection";

type MapData = NonNullable<Scene["map"]>;
type Place = { name: string; lat: number; lon: number };

const outline = japan as unknown as LonLat[][];

/** 描画に使う座標(ズームの対象) */
function targets(map: MapData): LonLat[] {
  switch (map.type) {
    case "route":
      return [map.from, map.to].map((p) => [p.lon, p.lat] as const);
    case "polygon":
      return [
        ...map.rings.flat(),
        ...(map.markers ?? []).map((p) => [p.lon, p.lat] as const),
      ] as LonLat[];
    case "points":
      return map.points.map((p) => [p.lon, p.lat] as const);
  }
}

/** 点列を SVG の path にする。範囲外・不正な点は飛ばす */
function ringPath(ring: readonly LonLat[], view: View, close: boolean): string {
  const pts = ring.flatMap(([lon, lat]) => {
    const p = project(lon, lat, view);
    return p ? [p] : [];
  });
  if (pts.length === 0) return "";
  return (
    pts
      .map(
        ([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`,
      )
      .join("") + (close ? "Z" : "")
  );
}

function Label({
  place,
  view,
  dy = -2.2,
}: {
  place: Place;
  view: View;
  dy?: number;
}) {
  const p = project(place.lon, place.lat, view);
  if (!p) return null;
  return (
    <text className="mapLabel" x={p[0]} y={p[1] + dy} textAnchor="middle">
      {place.name}
    </text>
  );
}

function Dot({ place, view, r }: { place: Place; view: View; r: number }) {
  const p = project(place.lon, place.lat, view);
  if (!p) return null;
  return <circle className="mapDot" cx={p[0]} cy={p[1]} r={r} />;
}

/** 港から港への弧(2 次ベジェ。弦の中点から、弦の長さの 25% だけ北側へふくらませる) */
function arcPath(
  a: readonly [number, number],
  b: readonly [number, number],
): string {
  const mx = (a[0] + b[0]) / 2;
  const my = (a[1] + b[1]) / 2;
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len = Math.hypot(dx, dy);
  if (len === 0) return `M${a[0]} ${a[1]}`;
  let nx = -dy / len;
  let ny = dx / len;
  if (ny > 0) {
    nx = -nx;
    ny = -ny; // 画面の上側へ
  }
  const cx = mx + nx * len * 0.25;
  const cy = my + ny * len * 0.25;
  return `M${a[0].toFixed(2)} ${a[1].toFixed(2)}Q${cx.toFixed(2)} ${cy.toFixed(2)} ${b[0].toFixed(2)} ${b[1].toFixed(2)}`;
}

/** シーンの map を描く。日本の輪郭を薄く敷き、航路(弧)・範囲(塗り)・点を重ねる。map が null なら何も出さない */
export function SceneMap({ map }: { map: Scene["map"] }) {
  if (!map) return null;
  const view = fitView(targets(map));

  let overlay: React.ReactNode = null;
  if (map.type === "route") {
    const a = project(map.from.lon, map.from.lat, view);
    const b = project(map.to.lon, map.to.lat, view);
    overlay = (
      <>
        {a && b ? <path className="mapRoute" d={arcPath(a, b)} /> : null}
        <Dot place={map.from} view={view} r={1.3} />
        <Dot place={map.to} view={view} r={1.3} />
        <Label place={map.from} view={view} />
        <Label place={map.to} view={view} />
      </>
    );
  } else if (map.type === "polygon") {
    overlay = (
      <>
        <path
          className="mapArea"
          d={map.rings
            .map((r) => ringPath(r as unknown as LonLat[], view, true))
            .join("")}
        />
        {(map.markers ?? []).map((m, i) => (
          <g key={i}>
            <Dot place={m} view={view} r={1.3} />
            <Label place={m} view={view} />
          </g>
        ))}
      </>
    );
  } else {
    overlay = map.points.map((p, i) => (
      <g key={i}>
        <Dot place={p} view={view} r={1 + (p.size ?? 0.5) * 2.5} />
        <Label place={p} view={view} dy={-(2.2 + (p.size ?? 0.5) * 2.5)} />
      </g>
    ));
  }

  return (
    <svg
      className="sceneMap"
      data-map-type={map.type}
      viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
      role="img"
      aria-label="地図"
    >
      {/* 輪郭は外周のみ。viewBox の外は自然に切れる */}
      <path
        className="mapOutline"
        d={outline.map((r) => ringPath(r, view, true)).join("")}
      />
      {overlay}
    </svg>
  );
}
