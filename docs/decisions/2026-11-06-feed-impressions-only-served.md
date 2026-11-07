# /api/feed は、実際に配信できた動画だけを impressions に記録する

- 日付: 2026-11-06
- Issue: #47
- 決定: recsys が選んだ動画のうち、`videos` に `status = 'ok'` で存在するものだけを返し、`impressions` にも同じものだけを記録する(設計書 §6.1 の手順 4 は「記録してから読む」順だが、読んでから記録する)。recsys の索引が DB より古く、公開で消えた・除外された動画が混ざったときに、見せていない動画を「配信済み」にしないため。全部ない場合は 503。`seenReset: true` のときの `impressions` の削除と記録は 1 トランザクションで行い、競合(`UNIQUE (anon_id, video_id)`)は `ON CONFLICT DO NOTHING` で無視する。
- 理由: 配信していない動画を `seenIds` に入れると、その動画が二度と選ばれなくなるため。
