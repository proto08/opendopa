# クラスタ名・色の材料は scenes.jsonl から取る

- 日付: 2026-11-06
- Issue: #37
- 決定: 機械的なクラスタ名の「地域・種別」は、`scenes.jsonl` の `chips` の最頻値、データ名は `categoryName`、色は `color` を使う。`videos.jsonl`(#33 の出力)は拡張しない。LLM が失敗・空返答のときも機械的な名前にする。
- 理由: シーンに既に地域・種別(chips)と色が入っており、DB の `videos` 行の形を変えずに済むため。
