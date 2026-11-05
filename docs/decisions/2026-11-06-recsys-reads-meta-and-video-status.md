# recsys は meta と videos.status も読む(embeddings_hnsw は作る)

- 日付: 2026-11-06
- Issue: #36
- 決定: recsys のロールに `meta` の SELECT(既に付与済み)と `videos.status` 列の SELECT(新しいマイグレーション `grant_recsys_videos_status`)を与え、設計書 §6.6 の読み取り対象に `meta`(`key='centroid'`)と `status` を足した。`embeddings_hnsw` は設計書どおり作る(recsys は使わない)。`scene` などの列は読めないまま。検証は `mise run db-test`。
- 理由: §7.2 で `u0 = meta.centroid` を使うのに、§6.6 の読み取り対象に `meta` がなかった。重心を `embeddings` から再計算するより、publish が書いた値を読むほうが単純で一貫する。`status='excluded'` の動画を候補から外すのに `status` が要る。
- 関連: ADR-0013 A3(`videos.status` を足した点を更新する)
