# 内航海運 2 データセット(naiko_route・naiko_ship)の絞り込みと出す数字

- 日付: 2026-11-06
- Issue: #55
- 決定:
  - `naiko_route`: 実データの座標の列名は `DISCHARGE PORT_LATITUDE/LONGITUDE`(イシューの `UNLOADING PORT_...` ではない)。港の緯度経度は、`derived` の新しい op `fill_by_key` で、欠損なら同じ港名の他の行(積み港・降ろし港のどちらの列でも)の値で補う。補っても座標がない行は `filters` で除く。
  - `naiko_route`: `YEAR` が 2017〜2023 の行だけ。積載率が 1(100%)を超える行(実データで 9 行。最大 1.51)は外れ値として除く。0 は除かない。積載率は `derived` の新しい op `scale`(×100、小数 1 桁)で % にして読む。
  - `naiko_route`: 距離・貨物の重さ・標本数は原稿に出さない。標本数は選定の点数(多い順)と、型の規則(`SAMPLE_SIZE > 10000` なら `busy_route`)にだけ使う。型は 4 つ(`high_load`・`large_ship`・`busy_route`・`standard`)で、決定モデルを使わず規則(`by_size`)で選ぶ。
  - `naiko_route` の実データでの件数: 47,510 行のうち、2017〜2023 年の外が 4 行(2013〜2016 年)、座標が取れない行が 32,474 行(積み港 21,178・降ろし港 11,296)、積載率が 1 超が 9 行で、フィルタで除くのが合計 32,487 行。残る 15,023 行から 150 本を選び、すべて品質ゲートを通った(数字の不一致 0、15 秒)。港名で補えた行は 0 行(座標が欠けた港は、どの行にも座標がない)。
  - `naiko_route` は同じ航路の別の年も、別の動画になりうる(実データの 150 本は 74 航路)。同じ航路を 1 本にまとめる選定は、このイシューではしない。
  - `naiko_ship`: `Address`・`Business_Management_ID`・`Ship_ID` は原稿にも元の行の表示(`hide`)にも出さない。`Launch_Year_(20` は `LAUNCH_BAND` に置き換え、`Deadweight_Tonnage`・`Horsepower` は 0 を欠損にする。選定は `seed: 42` のランダムを、`Supervisory_Transport_Bureau` と `Ship_Type_1` でばらして 150 本。型は総トン数・全長の大きさで 4 つ(`large_ship`・`long_ship`・`small_ship`・`standard`)。
  - `naiko_ship` は、元の CSV(`data/raw/naiko_ship/`)がなく、実データでは実行していない。列名は docs/data.md §10.8 とイシューにあるものだけを使い、合成した CSV でテストした。実データを置いたら `generate` の件数と品質ゲートを確かめる。
- 理由: イシュー #55 と docs/data.md §10.7・§10.8 の指示どおり。単位が確認できない列(距離・貨物の重さ・標本数)は、読み上げない(設計書 §0.2)。
