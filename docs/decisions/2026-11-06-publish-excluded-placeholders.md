# 除外の動画は、NOT NULL の列に空の値を入れて `videos` に入れる

- 日付: 2026-11-06
- Issue: #38
- 決定: scene がない除外の行は、`scene='{}'`、`category_name=''`、`headline=''`、`duration_sec=0`、`kind` は YAML の kind(省略時は grain から)にする。`status='excluded'` と `excluded_why` は `videos.jsonl` のとおり。
- 理由: テーブル定義は scene などが NOT NULL。除外の行を理由つきで DB に残す(イシューの要求)ため、配信しない前提の空の値で埋める。recsys と web は `status='ok'` だけを使う。
