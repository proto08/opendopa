// world-atlas の countries-50m.json から日本の輪郭だけを取り出し、lib/data/japan.json に書く。
// 使い方: node scripts/build-japan.mjs <countries-50m.json のパス>
// (npm pack world-atlas@2.0.2 で取得。ISC ライセンス、元データは Natural Earth = パブリックドメイン)
import { readFileSync, writeFileSync } from "node:fs";

const topo = JSON.parse(readFileSync(process.argv[2], "utf8"));
const { scale, translate } = topo.transform;

// arcs は差分符号化されている
const arcs = topo.arcs.map((arc) => {
  let x = 0;
  let y = 0;
  return arc.map(([dx, dy]) => {
    x += dx;
    y += dy;
    return [x * scale[0] + translate[0], y * scale[1] + translate[1]];
  });
});

const ringOf = (indexes) => {
  const pts = [];
  for (const i of indexes) {
    const a = i >= 0 ? arcs[i] : [...arcs[~i]].reverse();
    pts.push(...(pts.length ? a.slice(1) : a));
  }
  return pts;
};

const japan = topo.objects.countries.geometries.find((g) => g.properties.name === "Japan");
const polygons = japan.type === "Polygon" ? [japan.arcs] : japan.arcs;

// 外周だけを使い、0.15 度未満の島は落とし、座標は小数 2 桁に丸める
const rings = [];
for (const poly of polygons) {
  const ring = ringOf(poly[0]).map(([lon, lat]) => [+lon.toFixed(2), +lat.toFixed(2)]);
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  const size = Math.max(Math.max(...lons) - Math.min(...lons), Math.max(...lats) - Math.min(...lats));
  if (size >= 0.15) rings.push(ring);
}
writeFileSync(new URL("../lib/data/japan.json", import.meta.url), JSON.stringify(rings));
console.log(rings.length, "rings,", rings.reduce((n, r) => n + r.length, 0), "points");
