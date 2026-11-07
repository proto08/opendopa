# ADR-0061 Application Insights の組み込み

- Issue: #61
- 日付: 2026-11-07
- 状態: 決定

## A1 web の計測は `@azure/monitor-opentelemetry` + `@opentelemetry/api`

- 決定: `apps/web/instrumentation.ts` で、`APPLICATIONINSIGHTS_CONNECTION_STRING` があるときだけ `useAzureMonitor` を呼ぶ。独自の計測(`/api/*` のスパンと応答時間、recsys 呼び出し)は `@opentelemetry/api` だけで書く(`apps/web/lib/telemetry.ts`)。`next.config.ts` の `serverExternalPackages` に `@azure/monitor-opentelemetry` を入れる。
- 理由: Next.js が公式に OpenTelemetry を案内しており、Azure 公式の Application Insights の OpenTelemetry ディストリビューションが 1 関数で Exporter まで設定する。独自の計測が API だけに依存するので、SDK が登録されていないローカル・テストでは何も起きず、テストでは API をモックして記録内容を確かめられる。旧 `applicationinsights` SDK は新規採用を勧められていない。

## A2 個人を特定する情報は送らない

- 決定: 属性は `telemetry.ts` の固定項目(メソッド、パス(クエリ文字列なし)、ステータス、recsys のパス、成否、エラーの種類)だけ。匿名 ID は Cookie にあるので記録せず、エラー文は UUID を `[id]` に置き換えて 500 字に切る。`csvRow` は渡さない。HttpError(400 など、想定内の入力ミス)は失敗の原因として記録しない。
- 理由: イシューの要件。匿名 ID はユーザーを追跡できる値のため。

## A3 recsys は tracing のまま、出力を JSON にする

- 決定: 標準出力が端末でないときは `tracing-subscriber` の JSON 形式で出す(端末では従来の形式)。axum のミドルウェア `access_log` で、メソッド・パス・ステータス・所要時間を出す(本文・ヘッダー・クエリは出さない。5xx は error、4xx は warn、`/healthz` の成功は debug)。recsys 自体には Application Insights の SDK を入れない。
- 理由: Container Apps は標準出力を Log Analytics に集めるので、追加の SDK や秘密が要らない。状態を持たず外部へ送らない recsys の方針(CLAUDE.md)とも合う。

## A4 `protobufjs` のビルドスクリプトは実行しない

- 決定: `pnpm-workspace.yaml` の `allowBuilds` で `protobufjs: false`。
- 理由: OpenTelemetry の依存として入る。postinstall はバージョン確認のみで、実行時に不要。
