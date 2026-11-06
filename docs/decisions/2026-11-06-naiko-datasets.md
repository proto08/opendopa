# 内航海運 2 データセット(naiko_route・naiko_ship)の絞り込みと出す数字

- 日付: 2026-11-06
- Issue: #55
- 決定:
  - `naiko_route`: 実データの座標の列名は `DISCHARGE PORT_LATITUDE/LONGITUDE`(イシューの `UNLOADING PORT_...` ではない)。港の緯度経度は、`derived` の新しい op `fill_by_key` で、欠損なら同じ港名の他の行(積み港・降ろし港のどちらの列でも)の値で補う。補っても座標がない行は `filters` で除く。
  - `naiko_route`: `YEAR` が 2017〜2023 の行だけ。積載率が 1(100%)を超える行(実データで 9 行。最大 1.51)は外れ値として除く。0 は除かない。積載率は `derived` の新しい op `scale`(×100、小数 1 桁)で % にして読む。
  - `naiko_route`: 距離・貨物の重さ・標本数は原稿に出さない。標本数は選定の点数(多い順)と、型の規則(`SAMPLE_SIZE > 10000` なら `busy_route`)にだけ使う。型は 4 つ(`high_load`・`large_ship`・`busy_route`・`standard`)で、決定モデルを使わず規則(`by_size`)で選ぶ。
  - `naiko_route` の実データでの件数: 47,510 行のうち、2017〜2023 年の外が 4 行(2013〜2016 年)、座標が取れない行が 32,474 行(積み港 21,178・降ろし港 11,296)、積載率が 1 超が 9 行で、フィルタで除くのが合計 32,487 行。残る 15,023 行から 150 本を選び、すべて品質ゲートを通った(数字の不一致 0、15 秒)。港名で補えた行は 0 行(座標が欠けた港は、どの行にも座標がない)。
  - `naiko_route` は同じ航路の別の年も、別の動画になりうる(実データの 150 本は 74 航路)。同じ航路を 1 本にまとめる選定は、このイシューではしない。
  - `naiko_ship`: `Address`・`Business_Management_ID`・`Ship_ID` は原稿にも元の行の表示(`hide`)にも出さない。`Launch_Year_(20` は `LAUNCH_BAND` に置き換え、`Gross_Tonnage`・`Deadweight_Tonnage`・`Length`・`Horsepower` は 0 を欠損にする(実データで `Length` の 0 が 1,299 行あり、直す前は「全長は0メートル」が 65 本に出た。`Gross_Tonnage` の 0 は 2 行)。選定は `seed: 42` のランダムを、`Supervisory_Transport_Bureau` と `Ship_Type_1` でばらして 150 本。型は総トン数・全長の大きさで 4 つ(`large_ship`・`long_ship`・`small_ship`・`standard`)。
  - `naiko_ship` の実データでの確認: 列名は docs/data.md §10.8 のとおりで、すべて合った(2,710 行、UTF-8 BOM 付き)。`Ship_Type_1` 欠損 20 行・`Gross_Tonnage` 欠損/0 が `filters` で除かれ(24 行)、選定の 150 本のうち 4 本は内容の重複で除外、生成は 146 本(`generate --provider rules`)。品質ゲートの数字の不一致は 0、判断のフォールバックは 150 件中 0 件(型は規則)。推定秒数は最小・中央・最大とも 15 秒。型の内訳は large_ship 35・long_ship 1・small_ship 50・standard 60(`Length` の 0 を欠損にしたので、全長 80m 超の船が少なく long_ship は 1 本)。
  - 既知の差: `Ship_Type_1` に `土・砂利・石材専用船`(102 行)と `土･砂利･石材専用船`(半角の中点、9 行)の 2 表記がある。このイシューでは正規化せず、そのまま表示する。
- 理由: イシュー #55 と docs/data.md §10.7・§10.8 の指示どおり。単位が確認できない列(距離・貨物の重さ・標本数)は、読み上げない(設計書 §0.2)。
