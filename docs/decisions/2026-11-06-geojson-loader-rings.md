# GeoJSON ローダは、properties を平坦化し、座標を `rings` 列に持つ

- 日付: 2026-11-06
- Issue: #56
- 決定: `.geojson` のローダ(`ingest.read_geojson`)は、`properties` を列にし(値は CSV と同じ文字列。`null` は欠損)、`geometry` の座標を `rings`(`[[[lon,lat],...],...]`)列に入れる。`MultiPolygon` は全多角形の輪を 1 つのリストにまとめ、3 つ目の値(高度)は捨てる。`Polygon` / `MultiPolygon` 以外は欠損。リストの列は数値化しない。シーンの `map` は `{type: polygon, rings: <列名>, markers: [...]}` で作る。
- 理由: スキーマ(`PolygonMap`)の `rings` は輪のリストで、サンプルの 2 件が `MultiPolygon` だったため。多角形ごとに分けるより、地図側が輪を順に描くだけで済む。
