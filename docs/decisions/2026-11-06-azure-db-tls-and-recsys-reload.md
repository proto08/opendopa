# Azure の DB 接続は libpq 互換の sslmode にし、recsys の再読み込みは make recsys-reload で行う

- 日付: 2026-11-06
- 決定:
  1. web の `DATABASE_URL`(`infra/main.tf` の `database_url`)の末尾を `?sslmode=require&uselibpqcompat=true` にする。`apps/web/lib/db.ts` は変えない。
  2. publish 後の recsys の再読み込みは、`make recsys-reload`(`terraform output` で resource group 名と recsys アプリ名を取り、アクティブなリビジョンを `az containerapp revision restart` で再起動)で行う。`publish` の reload 失敗の警告文と README にこの手順を案内する。
  3. recsys を外部公開して `/internal/reload` を直接呼ぶ案は採らなかった。認証付きの内部 API を公開側に変えることになり、ユーザーの承認が要るため。recsys の ingress は内部のみ(`external_enabled = false`)のまま。
- 理由:
  - `pg` 8.x(pnpm-lock.yaml では pg 8.23.1 / pg-connection-string 2.14.1)は、`sslmode=require` を `verify-full` の別名(証明書検証あり)として扱う。Azure Database for PostgreSQL の証明書チェーンの切り替えで、接続できなくなる恐れがある。`uselibpqcompat=true` を付けると libpq と同じ意味(暗号化のみ・検証なし)になる。pg-connection-string 2.14.1 のソース(`index.js` と README)で `uselibpqcompat=true` に対応していることを確認した。ハッカソン用の構成で、動くことを優先する(証明書検証は行わない)。
  - recsys は内部のみで、手元 PC や CI からの `/internal/reload` は届かず、警告だけで済んでしまう。起動時に索引を読む作りなので、再起動で新しい索引になる。
- 未確認: `az` がこの環境になく、`make recsys-reload` の `az containerapp revision list/restart` のオプション(`--revision`、`--query "[?properties.active].name | [0]"`)は実機で未確認。web の接続(`uselibpqcompat`)も Azure 上では未確認(terraform apply 後に `/api/health` で確認する)。
- 関連: ADR-0018
