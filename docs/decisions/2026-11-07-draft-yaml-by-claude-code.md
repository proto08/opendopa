# 列定義 YAML の下書きは Claude Code が書き、draft-yaml は材料の出力と機械検査だけにする

- 日付: 2026-11-07
- Issue: #57
- 決定: `opendopa draft-yaml` は LLM を呼ばない。`--dataset <id>`(または `--file`)で、プロファイル・サンプル 10 行・スキーマの説明・禁止事項を `out/<id>/draft_prompt.md` に出し、`--check <file>` で、書かれた YAML を機械検査する(違反があれば終了コード 1)。下書きは Claude Code が材料を読んで `datasets/<id>.draft.yaml` に書く。検査は従来どおり、YAML の構文・穴 `{名前}` が列・`derived`・`stats` にあるか・`DatasetDef` のスキーマ(型ごとの `short: true` など)・`validate_against_columns`(#29)。`LLM_PROVIDER` による分岐と、下書きの先頭に違反コメントを書き込む処理は削除した。受け入れ条件は「`LLM_PROVIDER=azure` で下書きが出る」から「材料が出て、書かれた YAML を機械検査できる」に変える
- 理由: Azure OpenAI を使わない方針にしたため。列定義 YAML は 1 データセットに 1 本(数十〜百行)で、14 データセットはすでに揃っており、追加は稀なので、LLM API の部品を持たなくても、Claude Code が書けば足りる。材料と検査はそのまま使える。未確認の LLM 呼び出しを main に入れない
- 関連: 2026-11-06-draft-yaml-command.md(LLM を呼ぶ前提だった旧決定。検査の中身は引き継ぐ)
