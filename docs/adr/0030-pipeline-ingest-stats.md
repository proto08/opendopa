# ADR-0030 パイプライン: 取り込み・クリーニング・derived・stats・fmt

- Issue: #30
- 日付: 2026-11-04
- 状態: 決定

## A1 処理の順は 取り込み → derived → filters → (group 集計) → stats

- 決定: `prepare()`(`prepare.py`)は、読み込み → `derived` → `filters` → `grain: group` の集計 → `stats` の順に行う。`derived` を `filters` より先にするのは、`filters` の式が `derived` の名前を使えるようにするため。
- 理由: `derived` は行ごとの変換で、行を落とす前に作っても結果が変わらない。一方 `stats`(順位・合計)は、落とした後の行で数えないと件数や順位がずれる。

## A2 行の識別子は `row_id`(読み込み順の 1 始まり)

- 決定: DataFrame の index を `row_id`(ヘッダを除く読み込み順、1 始まり)にし、`excluded.csv`(列: `row_id`, `reason`)と `numbers` はこの番号で行を指す。`grain: group` の集計後は、グループの並び順の 1 始まりの番号に振り直す。
- 理由: データセットによって `No.` のような ID 列がないため。元の CSV の行(ヘッダの次が 1)と対応づけやすい。

## A3 `filters` の意味

- 決定: `{col, not_null: true}` は欠損の行を落とす。式の形は、式が真になる行を残す。1 行につき最初に落とした理由だけを記録する。
- 理由: `docs/data.md` §10.5 の「`FISCAL_YEAR == 2025` と `TOTAL_RENTAL_TIMES > 0`」を、残す条件として読む。

## A4 `grain: group` の YAML

- 決定: トップレベルに `group_by`(列名のリスト)と `aggregate`(列名 → `sum`/`mean`/`min`/`max`/`first`/`count`)を足す。集計後の列は `group_by` と `aggregate` の列、元の行数 `n_rows` だけ。`sum` は全部欠損のグループを欠損にする。
- 理由: #29 のスキーマに `group_by` がなかった。E2(`rental_result`)の「都道府県別の合計」を書くのに必要。

## A5 `numbers` の記録の形

- 決定: 行の識別子 → 記録の一覧。記録は `{name, op, columns, operation, inputs, value, display}`。欠損の値は記録しない。`display` は `fmt:`(なければ op の既定: 順位→`rank`、率・割合→`percent`、件数→`count`、他は数値のまま)を通した文字列。
- 理由: 検証(#34)が、元の列の値から再計算して照合するため。シーンJSONの `numbers` の形(M1 で決める)は #33 で、この記録から作る。

## A6 stats の定義上の決め

- 決定: `yoy_ratio` は百分率(%)で、`(今年 - 前年) ÷ 前年の絶対値`。前年が 0 なら欠損。`rank_in_group` の同順位は同じ順位で次は飛ぶ(1, 1, 3)。`is_first_time` はグループの最初の行を偽にする。`series` は、その行の `order` 以前の最大12点。
- 理由: 仕様が決めていなかった点。前年が負の場合に符号が逆転しない、未来の値を含めない、などを優先した。

## A7 金額の表記

- 決定: 1桁の丸めで誤差が 0.5% を超えるときは、「1億400万円」のように下の単位まで書く。
- 理由: 「1.04億」を「約1億円」にすると 3.8% ずれ、誤差 0.5% 以内の条件を満たさないため。
