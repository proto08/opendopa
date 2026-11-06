# pipeline

CSV → 原稿 → シーンJSON → 埋め込み → DB への公開を行う Batch(Python)。コマンドの一覧は `mise exec -- uv run opendopa --help`。

## 新しいデータセットを足す

エンジン(コード)を変えずに足せる(docs/data.md §10.15)。計画書型のように、まだ届いていないデータもこの手順で足す。

1. `data/raw/<id>/` に CSV を置く(`data/` は git 管理外)。
2. 列を調べる: `uv run opendopa profile --dataset <id>`(型・欠損率・種類数・最長の文字数・役割・上位の値。`out/<id>/profile.json` にも出る)。
3. 列定義 YAML の下書きを作る: `uv run opendopa draft-yaml --dataset <id>`(CSV を直接指定するときは `--file <path>`)。
   - `datasets/<id>.draft.yaml` に出る。既にあるときは、人が直した内容を守るため上書きしない(`--force` で上書き)。
   - LLM に渡すのは、プロファイル・サンプル 10 行・YAML スキーマの説明(docs/data.md §8.3)・禁止事項。プロンプトは `pipeline/prompts/draft_yaml.md`(コードと分けてある。人が直してよい)。
   - **LLM が書くのは文章のひな型だけ。数字はエンジンが元データから入れる。** 実行時には LLM を呼ばない。
   - 出力は機械で検査する。YAML として不正、穴 `{foo}` の名前が列にも `derived` / `stats` にもない、型ごとの `short: true` がない、などの違反を、画面に一覧で出し、下書きの先頭にコメントとして残す。
   - `LLM_PROVIDER=azure` が必要(`AZURE_OPENAI_*` は `.env.example`)。`none` のときは、LLM を呼ばず、案内を出して終了する。下書きなしで手で書く(`datasets/_example.yaml` が最小の例)。
4. 人が下書きを確認して直し(先頭の違反コメントを消す)、`datasets/<id>.yaml` に置く。確認では、事実にないこと(原因・責任・被害の推測)が混ざっていないかを見る。
5. `uv run opendopa generate --dataset <id>` を実行し、品質ゲートの結果を見る。

### 自由記述が多いデータ(計画書型)

- 概要の文は、`derived` の `op: sentence` でそのまま字幕に使う。元データの文なので事実が変わらない。要約や言い換えを LLM に書かせない。
- 施策の種類など、分類が要るときは、判断モデル(`decisions` と `fallback_rules`。docs/data.md §8.3a、`DECIDER_PROVIDER`)で行う。
