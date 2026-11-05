# data

pipeline が読む元データの置き場。中身は git に入れない(`data/raw/` は `.gitignore` 済み)。

## 置き方

```
data/raw/<dataset_id>/<ファイル名>
```

- `<dataset_id>` と `<ファイル名>` は、`docs/data.md` §10.0 の表のとおり
  (例: `data/raw/accident/02_jikojyouhou.csv`)。
- 列定義 YAML(`datasets/<id>.yaml`)の `files` に、リポジトリのルートからの相対パスで書く。
- 文字コードは UTF-8(BOM 付きでよい)。列名は元のまま(英語)。
- 元のファイルは書き換えない。pipeline は読み込んだコピー上で処理する。

## 出力

生成物は `out/<dataset_id>/` に出る(`out/` も git 管理外)。取り込み・クリーニングで
落とした行は、`out/<dataset_id>/excluded.csv`(列: `row_id`, `video_id`, `stage`, `reason`, `detail`)に理由つきで残る。
`stage` は `clean`(取り込み・クリーニング)か `build`(選定以降。品質ゲートを含む)。
`row_id` は、ヘッダを除いた読み込み順の 1 始まりの番号。
