# pipeline

CSV → 原稿 → シーンJSON → 埋め込み → DB への公開を行う Batch(Python)。コマンドの一覧は `mise exec -- uv run opendopa --help`。

## 新しいデータセットを足す

エンジン(コード)を変えずに足せる(docs/data.md §10.15)。計画書型のように、まだ届いていないデータもこの手順で足す。

1. `data/raw/<id>/` に CSV を置く(`data/` は git 管理外)。
2. 列を調べる: `uv run opendopa profile --dataset <id>`(型・欠損率・種類数・最長の文字数・役割・上位の値。`out/<id>/profile.json` にも出る)。
3. 列定義 YAML の下書きを作る。
   - `uv run opendopa draft-yaml --dataset <id>`(CSV を直接指定するときは `--file <path>`)で、下書きの材料を `out/<id>/draft_prompt.md` に出す。このコマンドは LLM を呼ばない。
   - 材料は、プロファイル・サンプル 10 行・YAML スキーマの説明(docs/data.md §8.3)・禁止事項。プロンプトは `pipeline/prompts/draft_yaml.md`(コードと分けてある。人が直してよい)。
   - **Claude Code に材料を読ませて、`datasets/<id>.draft.yaml` を書かせる。** 書くのは文章のひな型だけ。数字はエンジンが元データから入れる。実行時には LLM を呼ばない。
   - 書かれた下書きを検査する: `uv run opendopa draft-yaml --dataset <id> --check datasets/<id>.draft.yaml`。YAML として不正、穴 `{foo}` の名前が列にも `derived` / `stats` にもない、型ごとの `short: true` がない、などを一覧で出し、違反があれば終了コード 1。直して、違反がなくなるまで繰り返す。
   - Azure OpenAI などの LLM API は使わない(設計判断。`docs/decisions/2026-11-07-draft-yaml-by-claude-code.md`)。`datasets/_example.yaml` が最小の例。
4. 人が下書きを確認して直し(先頭の違反コメントを消す)、`datasets/<id>.yaml` に置く。確認では、事実にないこと(原因・責任・被害の推測)が混ざっていないかを見る。
5. `uv run opendopa generate --dataset <id>` を実行し、品質ゲートの結果を見る。

### 自由記述が多いデータ(計画書型)

- 概要の文は、`derived` の `op: sentence` でそのまま字幕に使う。元データの文なので事実が変わらない。要約や言い換えを LLM に書かせない。
- 施策の種類など、分類が要るときは、判断モデル(`decisions` と `fallback_rules`。docs/data.md §8.3a、`DECIDER_PROVIDER`)で行う。

## Azure のジョブで動かす(Container Apps Job)

元 CSV を Blob に置き、ジョブを手動で起動すると、動画だけを洗い替える(Issue #144)。ハッカソンのデモ(2026-11-08)までは、手元から `opendopa all` を流す。

- **元 CSV の置き場**: Storage Account の非公開コンテナ `raw`(Terraform が作る。`RAW_BLOB_CONTAINER` で変えられる)。`raw/<dataset_id>/*.csv`(`.geojson` も可)に、**人が**置く。`<dataset_id>/` 直下のファイルを名前順にすべて読む(サブフォルダは読まない)。`<dataset_id>/` が空のデータセットがあると、動画が消えないよう、ジョブはエラーで止まる。
- **ローカルとの切り替え**: `RAW_SOURCE=local`(既定。`datasets/*.yaml` の `files`)/ `RAW_SOURCE=blob`(Blob から `data/raw/<dataset_id>/` に取り込み、その配下をすべて読む)。`opendopa fetch-raw` で取り込みだけもできる。`opendopa all` は `RAW_SOURCE=blob` のとき最初に取り込む。
- **決定モデル**: ジョブの環境変数 `DECIDER_PROVIDER`(Terraform の `pipeline_decider_provider` = `rules` / `strands_azure`)。失敗・低確信度で `rules` に戻る動作は設計書 §8.3a のまま。
- **洗い替え**: `videos` は `id` で upsert、`embeddings` と `clusters` は消して入れ直し、今回の出力にない動画は `excluded`(`unpublished`)にする。`impressions`・`view_events`・`like_events` は消さない。公開のあと、`RECSYS_URL`(ジョブは recsys の内部 URL に届く)の `/internal/reload` で recsys に読み直させる。
- **動画 ID と元 CSV の行順**: ID は `<dataset_id>-<連番4桁>` で CSV の行順に依存する。元 CSV を差し替えるときは、**既存の行の順序を保ち、増やす行は末尾に足す**(複数ファイルは名前順に結合されるので、ファイル名の順序も保つ)。publish は、既にある動画の元の行の内容が前回と違うと警告を出す(公開は止めない)。
- **音声**: ジョブの `TTS_PROVIDER` は `none`(VOICEVOX にジョブから届かない)。音声つきの動画にしたいデータセットは、手元から `opendopa all` で公開する。

### 手順(人が実行する。課金される)

1. `infra/terraform.tfvars` で `pipeline_job_enabled = true`(`enable_storage = true` が必要)にして `mise run infra-plan` → `mise run infra-apply`。
2. 元 CSV を Blob の `raw/<dataset_id>/` に置く(例: `az storage blob upload-batch -d raw --destination-path <dataset_id> -s <CSV のあるフォルダ> --account-name <storage>`)。
3. `make deploy-pipeline`(イメージを push してジョブを更新)。
4. `make pipeline-run`(ジョブを起動)。進み具合は `az containerapp job execution list -g <rg> -n <job> -o table`、ログは Log Analytics の `ContainerAppConsoleLogs_CL`。
5. 定期実行にしたいときは、ジョブを `schedule_trigger_config`(cron)に変える。ハッカソンの範囲では手動のみ。
