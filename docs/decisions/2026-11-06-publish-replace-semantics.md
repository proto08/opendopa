# publish の入れ替えは、embeddings・clusters は全削除して作り直し、videos は upsert する

- 日付: 2026-11-06
- Issue: #38
- 決定: 1 トランザクションで、datasets と videos を upsert、embeddings と clusters を全削除して挿入、meta の centroid を upsert する。今回の出力に無い動画は、行を消さず `status='excluded'`・`excluded_why='unpublished'` にする。Blob は DB より先に(上書きで)書く。
- 理由: `videos` は impressions・view_events・like_events から外部キーで参照され、消すと本番で失敗するため。embed は毎回全体をやり直すので、embeddings と clusters は差分にしない。Blob を先にするのは、DB が失敗しても配信に影響せず、やり直しで同じ結果になるため。
