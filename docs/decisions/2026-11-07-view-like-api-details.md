# /api/view と /api/like の細部

- 日付: 2026-11-07
- Issue: #48
- 決定:
  - `videoId` の存在は `status = 'ok'` の動画に限る(配信しない動画への視聴・いいねは 400)。`/api/like` も同じ。
  - いいねの「最新の状態と同じなら追加しない」判定と追加は、1 つのトランザクションの中で (anon_id, video_id) の `pg_advisory_xact_lock` を取り、別の文で最新の状態を読んでから追加する(同時に送られても二重に足さない)。1 文の CTE にすると、READ COMMITTED ではロック待ちのあとでも文の開始時のスナップショットで判定してしまい、二重に足しうる。
  - `viewId` が重複したときも 200 で、`logEntry.ratio` はそのリクエストの値から計算して返す(保存済みの行は読まない)。
  - `logEntry.headline` / `reasonLabel` / `liked` は、`videos`・`impressions`・最新の `like_events` から読む。
- 理由: 設計書に細部の指定がなく、テーブルに一意制約がない `like_events` で二重追加を防ぐには、ロックを取ったあとに最新の状態を読み直す必要がある。
