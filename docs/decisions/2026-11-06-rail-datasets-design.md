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
- 未確認: 実データ(`data/raw/rail_*`)がなかったため、生成件数・除外の内訳は実データでは測っていない。列名(`YEAR`、`CATEGORY`、`JURISDICTION` ほか)は `docs/data.md` と Issue の記述から。実データを置いたら `mise exec -- uv run opendopa generate --dataset <id>` で件数を確かめ、この決定に追記する。
