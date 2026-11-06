# flightplan: 意味が不確かなフラグ・単位が不明な列・ID は出さない

- 日付: 2026-11-06
- Issue: #56
- 決定: `FLIGHT_METHOD_NEAR_DANGER_ZONE` は意味を確認できていないので、ラベル(対応表)に入れない。そのため、これだけが立つ行は特徴なしとして除外する。`FLIGHT_ALTITUDE`・`FLIGHT_SPEED`・`FLIGHT_PLAN_ID_NEW`・`MANUFACTURING_NUMBER`・登録/更新日時・`rings` は、原稿に使わず `hide` で `csv_row` にも出さない。大きな数字は飛行時間(時間)。型は `bvlos` / `night` / `did` / `other` の 4 つで、飛行方法・空域のフラグのルール(`fallback_rules.flags`)で選ぶ。
- 理由: 設計書 §0.2・docs/data.md §10.2(単位の確認が取れるまで高度・速度を出さない、ID は出さない)に従うため。
