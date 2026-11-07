# publish は tags を upsert し、video_tags を全削除して作り直し、使われないタグを消す

- 日付: 2026-11-07
- Issue: #152
- 決定: 1 トランザクションの中で、`status='ok'` の動画のシーンJSON の `tags` から `tags` を upsert し、`video_tags` は全削除して挿入し直す。そのあと、どの動画にも付かないタグを消す。`yomi` と `sort` は、シーンJSON にないので `pipeline/opendopa_pipeline/tags.py` の表(都道府県は JIS の順、データ種別は定義順)から引く。
- 理由: `video_tags` は他から参照されないので、embeddings と同じ全削除・再挿入で、重複も古い行も残らない(再実行しても同じ結果)。`tags` は `video_tags` から参照されるため、`video_tags` を作り直したあとで消す。
