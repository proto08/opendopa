# 手元からのマイグレーションは一時的なファイアウォール規則で流す

- 日付: 2026-11-07
- 決定: README の再構築手順4に、自分の IP を一時許可する `az postgres flexible-server firewall-rule create` と、流した後に消す `delete` のコマンドを書いた。`dbmate up` はリポジトリのルートで `mise exec -- dbmate up` として流す。
- 理由: Postgres は Azure 内サービスからのみ許可しており、CI にマイグレーションの job がないため、手元から流す手順が具体的でないと「ゼロから再現できる」手順にならない(PR #139 のレビュー指摘)。サーバー名は root の出力に無いので、`postgres_fqdn` の先頭ラベルから取る。
