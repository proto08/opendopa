# API の入力検証には zod を使う

- 日付: 2026-11-06
- Issue: #46
- 決定: Route Handler の本文・クエリの検証に `zod`(v4)を使う。検証の失敗は `HttpError(400)` にして `{ "error": "..." }` で返す。
- 理由: スキーマから型が得られ、`lib/http.ts` の `parseJsonBody` / `parseQuery` で各 API が 1 行で検証できる。
