# 鉄軌道の損益・貸借: 生成件数と除外の内訳(実データ)

- 日付: 2026-11-06
- Issue: #54
- 決定: `generate`(`DECIDER_PROVIDER=rules`)の結果を次のとおり記録する。いずれも数字の不一致(`number_mismatch`)は 0、推定秒数は 15〜30 秒、警告なし。
  - `rail_pl`: 生成 145 本(選定 150 から、営業収益が欠損の 5 行を除外)。ほかに、営業損益が欠損・0 の 6 行を取り込みの段階で除外(`filter`)。型は profit 79 / loss 61 / first_profit 3 / first_loss 2。推定秒数は最小 15.0 / 中央 15.0 / 最大 19.38。
  - `rail_income`: 生成 146 本(営業収益が欠損の 4 行を除外)。純損益が欠損・0 の 64 行を `filter` で除外。型は profit_diversified 60 / profit_rail 46 / loss_diversified 20 / loss_rail 20。推定秒数は最小 15.0 / 中央 16.15 / 最大 19.69。
  - `rail_bs`: 生成 150 本。自己資本比率が欠損・0 の 29 行を `filter` で除外。型は equity_low 110 / equity_high 28 / equity_negative 12(equity_over は 2023 年を中心にした選定に入らない)。推定秒数は最小 15.0 / 中央 15.0 / 最大 15.08。
- 理由: イシュー #54 の受け入れ条件(生成件数・除外の内訳を記録する)。
