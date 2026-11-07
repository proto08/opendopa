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
