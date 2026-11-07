# pipeline を Container Apps Job にし、元 CSV は Blob の raw コンテナから読む

- 日付: 2026-11-07
- Issue: #144
- 決定:
  - 元 CSV は Storage Account の非公開コンテナ `raw`(Terraform で作る。中身は人が置く)の `<dataset_id>/` 直下に置く。`RAW_SOURCE=blob` のとき、そこを `data/raw/<dataset_id>/` に取り込み、配下の `.csv` / `.geojson` を名前順にすべて読む(YAML の `files` は使わない)。既定の `RAW_SOURCE=local` は従来どおり `files`。接続は既存の `STORAGE_CONNECTION_STRING` を使う。
  - ジョブは `infra/modules/pipelinejob`(`pipeline_job_enabled`、既定 false。手動起動のみ、スケジュールなし)。`opendopa all` を実行し、決定モデルは `pipeline_decider_provider`(`DECIDER_PROVIDER`)で切り替える。TTS は `none`、埋め込みは Azure OpenAI。
  - 洗い替えは `publish.py` の現在の動作のまま(`videos` は upsert、`embeddings`・`clusters` は入れ直し、履歴のテーブルは触らない)。recsys の reload は publish が内部 URL に POST する。
  - 動画 ID は行順に依存するため、ID の付け方は変えず、「既存の行の順序を保つ(増やす行は末尾)」を運用の約束にする。保険として、publish は既存の動画の `csv_row` が前回と違うと警告を出す。
- 理由: ID の付け方を変えると既存の履歴が壊れ、デモ(2026-11-08)の直前に大きく動かせない。警告があれば、行順が崩れたことに気付ける。ジョブの TTS を `none` にしたのは、VOICEVOX にジョブから届かないため(音声つきの動画は手元から公開する)。
- 注意: `terraform validate` のみ実行した。plan / apply、イメージの push、ジョブの起動は、課金と Azure の資格情報が要るため実行していない。
