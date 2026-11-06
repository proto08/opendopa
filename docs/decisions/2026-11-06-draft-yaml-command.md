# draft-yaml は、既存の列定義を検証する仕組みで LLM の出力を検査し、違反を下書きの先頭に残す

- 日付: 2026-11-06
- Issue: #57
- 決定: `opendopa draft-yaml` は、LLM の出力から ①YAML の構文 ②穴 `{名前}` が列・`derived`・`stats` にあるか ③`DatasetDef` のスキーマ検査(型ごとの `short: true` など) ④`validate_against_columns`(#29)を検査する。違反があっても下書きは書き出し、違反を先頭の `#` コメントと画面の一覧で示す。既存の下書きは、`--force` がなければ上書きしない(`decide --draft` と同じ)。プロンプトは `pipeline/prompts/draft_yaml.md`、YAML スキーマの説明は `docs/data.md` §8.3 を実行時に読んで渡す(二重管理しない)。
- 理由: 違反のある下書きでも、人が直す出発点としては役に立つため、捨てずに残す。穴の検査は、YAML 全体の検証が失敗しても結果が出るよう、独立して行う。LLM が使えない(`LLM_PROVIDER=none`)ときは、終了コード 1 で案内だけ出す(下書きなしで手で書けばよいため、エラー(2)にはしない)。
