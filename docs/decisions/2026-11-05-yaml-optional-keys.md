# YAML に省略可のキーを足す

- 日付: 2026-11-05
- Issue: #33
- 決定: YAML に省略可のキー `kind` `headline` `chips` `sparkline` `map` `hide` を足した。`map` は `route` と `points` のみ(`polygon` は GeoJSON の #56 で)。`comments.rule` の構文(`式 -> プール; else プール`)は読み込み時に検査する。
- 理由: イシューの「YAML の指定があれば作る」を実現する指定がスキーマになかったため。
