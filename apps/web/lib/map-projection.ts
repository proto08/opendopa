/**
 * 地図の投影と自動ズーム(純粋な関数)。
 * 投影は等緯度経度(equirectangular)で、経度を cos(基準緯度) で縮める。日本の範囲なら歪みが小さく、
 * 計算が軽いので使う(docs/decisions/2026-11-06-scene-map-projection.md)。
 */

/** 基準緯度(日本の中央あたり) */
export const REF_LAT = 36;
/** SVG の viewBox の大きさ */
export const MAP_WIDTH = 100;
export const MAP_HEIGHT = 68;

const COS_REF = Math.cos((REF_LAT * Math.PI) / 180);

export type LonLat = readonly [lon: number, lat: number];

/** 投影した平面(経度は cos で縮め、緯度は上が小さくなるよう反転)上の範囲 */
export type View = {
  minX: number;
  minY: number;
  width: number;
  height: number;
};

/** 緯度経度 → 投影平面。有限でない値は null */
export function toPlane(lon: number, lat: number): [number, number] | null {
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
  return [lon * COS_REF, -lat];
}

/** 投影平面 → SVG 座標 */
export function planeToSvg(x: number, y: number, view: View): [number, number] {
  return [
    ((x - view.minX) / view.width) * MAP_WIDTH,
    ((y - view.minY) / view.height) * MAP_HEIGHT,
  ];
}

/** 緯度経度 → SVG 座標。有限でない値は null。範囲外(海外など)でもそのまま計算する */
export function project(
  lon: number,
  lat: number,
  view: View,
): [number, number] | null {
  const p = toPlane(lon, lat);
  return p ? planeToSvg(p[0], p[1], view) : null;
}

/** 対象が占める最小の幅(度)。1 点や小さな範囲を拡大しすぎない */
const MIN_SPAN_DEG = 1.5;
const PADDING = 0.18;

/**
 * 対象の点が(余白つきで)すべて収まり、MAP_WIDTH:MAP_HEIGHT の比になる範囲を返す。
 * 小さな範囲は拡大され、MIN_SPAN_DEG より小さくはならない。有効な点がなければ日本全体。
 */
export function fitView(coords: readonly LonLat[]): View {
  const planes = coords.flatMap(([lon, lat]) => {
    const p = toPlane(lon, lat);
    return p ? [p] : [];
  });
  if (planes.length === 0) return JAPAN_VIEW;

  const xs = planes.map((p) => p[0]);
  const ys = planes.map((p) => p[1]);
  const minSpan = MIN_SPAN_DEG * COS_REF;
  let width =
    Math.max(Math.max(...xs) - Math.min(...xs), minSpan) * (1 + PADDING * 2);
  let height =
    Math.max(Math.max(...ys) - Math.min(...ys), MIN_SPAN_DEG) *
    (1 + PADDING * 2);
  // viewBox の縦横比に合わせて、足りない方を広げる(はみ出さない)
  const aspect = MAP_WIDTH / MAP_HEIGHT;
  if (width / height < aspect) width = height * aspect;
  else height = width / aspect;

  const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
  const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  return { minX: cx - width / 2, minY: cy - height / 2, width, height };
}

/** 日本全体を収める既定の範囲(東経 122〜154 度、北緯 24〜46 度) */
export const JAPAN_VIEW: View = fitView([
  [122, 24],
  [154, 46],
]);
