# publish は psycopg 3 と azure-storage-blob を使う

- 日付: 2026-11-06
- Issue: #38
- 決定: DB は `psycopg[binary]`(ベクトルは pgvector のテキスト形式 `'[..]'::vector` で渡し、pgvector パッケージは足さない)、Blob は `azure-storage-blob`、recsys の reload は標準ライブラリの `urllib`。
- 理由: 依存を最小にするため。psycopg 3 は `with connect()` が例外でロールバックするので、トランザクションの扱いが単純。
