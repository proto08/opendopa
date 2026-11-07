# /api/view と /api/like の細部

- 日付: 2026-11-07
- Issue: #48
- 決定:
  - `videoId` の存在は `status = 'ok'` の動画に限る(配信しない動画への視聴・いいねは 400)。`/api/like` も同じ。
  - いいねの「最新の状態と同じなら追加しない」判定と追加は、1 文の SQL で行い、(anon_id, video_id) の `pg_advisory_xact_lock` で直列化する(同時に送られても二重に足さない)。
  - `viewId` が重複したときも 200 で、`logEntry.ratio` はそのリクエストの値から計算して返す(保存済みの行は読まない)。
  - `logEntry.headline` / `reasonLabel` / `liked` は、`videos`・`impressions`・最新の `like_events` から読む。
- 理由: 設計書に細部の指定がなく、テーブルに一意制約がない `like_events` で二重追加を防ぐには、判定と追加を同時に行う必要がある。
