# `all` は generate → tts → embed → publish の順に実行する

- 日付: 2026-11-06
- Issue: #60
- 決定: `opendopa all` の順序を generate → tts → embed → publish にする。`tts` を単体で実行して動画が除外されたときは、`embed` のやり直しが必要な旨を出力に表示する
- 理由: `tts` は長さ超過の動画を `videos.jsonl` で `excluded` にするが、`embed` が先だと除外された動画の埋め込みが残り、`publish` の整合検査(埋め込みと `status='ok'` の一致)で失敗するため。`embed` は `status='ok'` の動画だけを読むので、`tts` のあとに実行すれば除外が反映される
- 関連: 2026-11-06-tts-length-recheck
