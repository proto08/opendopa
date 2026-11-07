# タグは元データから機械的に作り、LLM を使わない

- 日付: 2026-11-07
- Issue: #157
- 決定: ハッシュタグは、データ種別を `datasets/<id>.yaml` の `tag:`、地域を `region_from:` の列の値と都道府県の正規化表(`pipeline/opendopa_pipeline/tags.py`)から作る。LLM は使わない。取れない動画には地域タグを付けず、元データにない地名は作らない。
- 理由: 設計書 §0.2(原稿の数字は元データから機械的に作る、実行時に LLM を呼ばない)と同じ考え方。タグは出典の一部として読まれるので、再実行で同じ結果になること、元データで確かめられることを優先した。
- 関連: `docs/decisions/2026-11-07-pipeline-tags-region-columns.md`、`docs/hashtag_design.md` §2、§3
