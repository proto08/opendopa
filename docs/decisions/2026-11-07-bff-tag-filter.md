# BFF のタグ絞り込みは、候補の外の配信済みを残し、未知のタグは recsys を呼ぶ前に 400 にする

- 日付: 2026-11-07
- Issue: #154
- 決定:
  - `GET /api/feed?tag=…` は、未知のタグ ID を `tags` で確かめて 400 にしてから、`video_tags` を AND(`HAVING count(DISTINCT tag_id) = 指定数`、`status = 'ok'` のみ)で引いて `candidateIds` にする。タグがなければ `candidateIds` を送らず、今と同じ動きにする。
  - 絞り込み中に recsys が `seenReset: true` を返したら、`impressions` は **候補の動画の分だけ**消す(`recordImpressions` の `scopeIds`)。候補の外の配信済みは残す。
  - `pool_empty` のときは、200 で `items: []`、`reason: "pool_empty"`、`taste`(と `includeMap=1` なら `map`)を返し、`impressions` には何も記録しない。
  - `tag` の重複は除いてから数える(同じ ID を 5 回指定しても 1 個)。`parseQuery` は、同じキーが繰り返されたら配列にする。
  - `GET /api/tags` は、動画がないタグも件数 0 で返す(並びは `sort`、`id`)。
- 理由: `seenReset` で全消しすると、絞り込み外の配信済みまで忘れて、絞り込みを外したときに同じ動画が出てしまう(#153 の決定が web に委ねた論点)。`pool_empty` は「見る動画がない」状態で、エラーではないので 200 にした(画面が案内を出す)。
- 関連: `docs/decisions/2026-11-07-recsys-candidate-ids.md`、`docs/hashtag_design.md` §5
