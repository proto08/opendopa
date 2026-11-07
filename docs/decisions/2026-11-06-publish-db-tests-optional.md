# publish の DB テストは TEST_DATABASE_URL があるときだけ動かす

- 日付: 2026-11-06
- Issue: #38
- 決定: pgvector 入りの PostgreSQL を `TEST_DATABASE_URL` で渡したときだけ DB を使うテストを実行し、なければスキップする。テストごとに一時スキーマを作って消す(マイグレーションの 02 を流す)。
- 理由: CI(#14 で追加予定)や手元で DB がなくても `mise run test` が通るようにしつつ、DB がある環境では実際の SQL・ロールバックを確かめるため。
