# 鉄軌道3データセット(rail_traffic1・rail_traffic2・rail_km)の作り方

- 日付: 2026-11-06
- Issue: #53
- 決定:
  - 事業者名の列名が、ファイルによって違う(`CORPORATION_NAME` / `COMPANY_NAME` / `OPERATOR_NAME`)ので、YAML の `rename` で3つとも `OPERATOR` にそろえる(ない列の rename は無視される)。
  - 選ぶのは `YEAR == 2023` の行だけ。順位・前年比・推移(`series`)は全年度で計算してから選ぶ。区分(`CATEGORY`)に1事業者しかない行は、順位を語れないので選ばない(`<順位>_n > 1`)。点数は、規模の順位(`rank_desc`)と前年比の絶対値(重み 0.02)。`CATEGORY` でばらして `cap=150`。
  - `zero_is_null` に、見出し指標の列を入れる(0 は「その輸送・事業がない」と読み、順位・前年比に入れない)。`null_values` は `["", "-", "－", "…"]`。
  - 型は4つずつ。型の選択は `decisions` の `template`(`rules` では上位3位に入る指標の型を優先し、なければ既定の型)。どの型も、数字は列と stats の値だけから作る。
  - 絶対値は、`rail_traffic1`(輸送人員・貨物のトン数)と `rail_traffic2` では出さない(前年比・順位・定期の割合だけ)。`rail_km` は営業キロ(km)を出し、列車数・車両数は順位と前年比だけ。
  - 前年比は「前年に比べて5.2%増えました/減りました」と語る。そのために stats の op `abs`(絶対値)と `sign_word`(正負で語を選ぶ。0 は欠損)を足した。前年比が 0% の行は、前年比の文を出さない。
  - `rank_in_group` が作る `<name>_n`(順位をつけた行数)を、穴と式で使えるように、`defined_names` に入れた。
- 理由: 元データの列名と単位が確定していない(単位は「要確認」)ので、Issue の指示どおり、確認できた値と計算値だけを語る。絶対値を出さない型は、単位が分かるまでの安全側の選択。
- 実データでの確認(2026-11-06): 3つとも UTF-8(BOM付き)。列名(`YEAR`・`CORPORATION_NAME`・`JURISDICTION`・`CATEGORY` と各指標の列)は YAML の推測どおりで、YAML は直していない。欠損は空欄(`""`)だけで、`-` などは出てこない(`null_values` の他の語は念のため残す)。年度は 2012〜2023。2023年度の行は rail_traffic1・rail_traffic2 が 334 行(中小205・大手88・公営34・JR7)、rail_km が 350 行(中小204・大手102・公営37・JR7)。行は路線単位の事業者名(例: 東急電鉄_東急新横浜線)を含む。
  - 生成件数(rules): rail_traffic1 146本(除外4: no_template 3・no_big_number 1)、rail_traffic2 146本(除外4: no_template 4)、rail_km 147本(除外3: no_template 3)。いずれも cap=150 から。
  - 型の内訳: rail_traffic1 は yoy 129・rank 11・commuter 6、rail_traffic2 は overview 122・passage 12・daykm 6・distance 6、rail_km は km 126・trains 12・cargo 7・cars 2。rules のフォールバックでは、先頭の型(yoy・overview・km)に偏る。
  - 数字の不一致(number_mismatch): 3つとも 0 件。
  - 推定秒数: 3つとも 最小・中央・最大 すべて 15.0 秒(30秒の上限以内)。
  - 除外は、どの型のテンプレートも埋められない行(欠損が多い事業者。貨物専業や休止など)。
  - 前年比が大きい行(新線の開業年で 2960.3% 増など)は、そのまま語る。元データの値から機械的に計算した結果であり、誤りではない。
