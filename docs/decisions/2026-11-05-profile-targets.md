# profile の対象は --dataset か --file

- 日付: 2026-11-05
- Issue: #31
- 決定: `profile` の対象は `--dataset <id>`(`datasets/<id>.yaml` の `files` を `load_frame` で読み、`rename` などを適用)か `--file <csv>`(複数可。YAML なしで、空欄だけ欠損として読む)。YAML がない `--dataset <id>` は `data/raw/<id>/*.csv` を読む(`accident` の YAML は未作成のため)。どちらも無い、または両方未指定は終了コード 2。出力先は `out/<id>/profile.json`(`--file` だけのときの id はファイル名の幹)。`--out-dir` で親を変えられる。
- 理由: docs/data.md §10.15 の「YAML を作る前に列を調べる」流れに合わせるため。
