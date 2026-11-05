# ADR-0018 Docker 化と Container Apps へのデプロイ

- Issue: #18
- 日付: 2026-11-06
- 状態: 決定

## A1 デプロイ方式: イメージ更新は `az containerapp update`(Terraform は差分を無視)

- 決定: `make deploy`(`mise run deploy`)が、docker build → ACR に push → `az containerapp update --image` の順に進める。イメージのタグは `git rev-parse --short HEAD`(`TAG=` で上書き可)。Terraform の `azurerm_container_app` は `lifecycle.ignore_changes = [template[0].container[0].image]` とし、`web_image` / `recsys_image` が空(既定)のときは公開のプレースホルダー `mcr.microsoft.com/k8se/quickstart:latest` で作る。
- 理由: レジストリへの push より前に Container Apps を作る必要があるため(初回の apply 時にイメージが存在しない)。`web_image_tag` を書き換えて `terraform apply` する方式だと、アプリの更新のたびに plan の確認と state ロックが要り、また他のリソースの差分も巻き込む。設計書 §12.2 の「どちらを使うか記録する」に従う。

## A2 レジストリはマネージド ID + AcrPull で引く

- 決定: ユーザー割り当てマネージド ID を作り、ACR に `AcrPull` を付けて、2 つの Container App の `registry` に指定する。ACR の管理者ユーザーは使わない(ADR-0016)。
- 理由: システム割り当てだとアプリを作った後でないと権限を付けられず、初回のイメージ取得が失敗する。

## A3 recsys は内部のみ。URL は環境の内部 FQDN

- 決定: recsys は `external_enabled = false`、最小・最大レプリカ 1(起動時に全動画をメモリへ読み込み、状態を持つため 2 台にしない)。web の `RECSYS_URL` は recsys の ingress の FQDN(`https://<app>.internal.<環境のドメイン>`)を Terraform が自動で設定する。VNet 統合はしない(ADR-0017 A1)。
- 理由: 同じ Container Apps Environment の中からだけ届き、外部から到達できない、という受け入れ条件を満たす最小の構成。

## A4 環境変数とシークレット

- 決定: シークレット(Container Apps の secret 経由)は、web が `DATABASE_URL`、`INTERNAL_TOKEN`、`APPLICATIONINSIGHTS_CONNECTION_STRING`、recsys が `INTERNAL_TOKEN`、`RECSYS_DATABASE_URL`(変数 `recsys_database_url` が空でないときだけ)。通常の環境変数は web が `MEDIA_BASE_URL`、`RECSYS_URL`、recsys が `PORT=8080`、`EMBED_DIM`。`INTERNAL_TOKEN` は変数 `internal_token`(`TF_VAR_internal_token`)で渡す。
- 理由: web・recsys とも実行時に Azure OpenAI / Speech を呼ばない(設計書 §0.2)ので、そのキーは渡さない。`RECSYS_DATABASE_URL` は読み取り専用ロール(マイグレーションで作る)ができてから渡す。recsys は現状 DB を読まないため、空でも起動する。

## A5 Dockerfile

- 決定: web は Next.js の `output: "standalone"`(`outputFileTracingRoot` はリポジトリのルート)、recsys は `rust` イメージでの release ビルド → `debian:trixie-slim`。どちらもビルドコンテキストはリポジトリのルート、非 root で動かす。pnpm は Node 26 に corepack がないため `npm install -g` で入れる。ビルドは `linux/amd64` を既定とする(Container Apps に合わせる)。
- 理由: mise.toml のバージョンと揃え、イメージを小さくするため。
