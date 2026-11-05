# accident の負傷の内容は、原稿・判断・元の行のどこにも出さない

- 日付: 2026-11-05
- Issue: #34
- 決定:
  - `CASUALTIES_SUMMARY` は、`derived.casualty_sentence`(「人的被害は、報告にありません。」か「負傷者の報告があります。」)にだけ変換して使う。
  - 判断モデル(`template`)の `state` には `CASUALTIES_SUMMARY` でなく `casualty_sentence` を渡す。
  - `hide: [CASUALTIES_SUMMARY]` で、`videos.csv_row` にも出さない。
  - 型 `injury` のテンプレートは、概要の2文目以降(`summary_2`)と機体の被害の行を使わない(負傷の部位や症状が書かれうるため)。
  - 負傷者ありの動画は `comments: []`(`comments.rule` で `none`)。
- 理由: 設計書 §15.2「負傷の部位や症状は読まない」。docs/data.md の YAML 例は `state` に `CASUALTIES_SUMMARY` を挙げていたが、モデルに負傷の内容を渡さずに済むので、定型文にしたものを渡す。
