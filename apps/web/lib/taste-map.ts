// 好みの地図の座標変換(純粋な関数)。recsys の座標(0〜1)を SVG の座標に直す。

/** SVG の viewBox の一辺 */
export const TASTE_MAP_SIZE = 100;
/** 縁の余白(点が枠にかからないように) */
export const TASTE_MAP_PAD = 6;

/** 0〜1 の座標を SVG 座標にする。範囲外・有限でない値は 0〜1 に丸める */
export function toSvg(x: number, y: number): [number, number] {
  const span = TASTE_MAP_SIZE - TASTE_MAP_PAD * 2;
  const c = (v: number) => (Number.isFinite(v) ? Math.min(Math.max(v, 0), 1) : 0);
  return [TASTE_MAP_PAD + c(x) * span, TASTE_MAP_PAD + c(y) * span];
}
