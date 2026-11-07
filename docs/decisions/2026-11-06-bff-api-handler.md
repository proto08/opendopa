# /api/* の共通要件は apiHandler で包んで満たす

- 日付: 2026-11-06
- Issue: #46
- 決定: `lib/http.ts` の `apiHandler` が、匿名 ID の Cookie(`od_aid`、UUID 形式でなければ再発行)、レート制限、エラー変換(`HttpError` はそのステータス、`RecsysError` は 502、その他は 500)、`Cache-Control: no-store` をまとめて行う。`/api/health` 系は、監視からの呼び出しに Cookie 発行とレート制限をかけたくないので包まず、`no-store` だけ自分で付ける。
- 理由: 新しい API が、ヘルパーを使うだけで §6.5 の共通要件を満たせるようにする(#46 の受け入れ条件)。
