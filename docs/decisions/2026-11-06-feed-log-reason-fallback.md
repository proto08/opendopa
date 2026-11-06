# taste.log の reasonLabel は impressions から引き、記録がなければ「—」

- 日付: 2026-11-06
- Issue: #47
- 決定: `taste.log[].reasonLabel` は、その動画の `impressions.reason` の表示名にする。`seenReset` で `impressions` が削除された後など、記録がない動画は「—」とする。`liked` は最新の `like_events` の状態で、記録がなければ `false`。ダミー API(`lib/feedDummy.ts`)は削除し、`REASON_LABELS` は `lib/reasons.ts` に移した。
- 理由: 設計書は `reasonLabel` の出どころを `impressions.reason` と定めており、削除後の表示は仕様にないため、誤った理由を出さない表示にした。
