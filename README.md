# OpenDopa

Progateハッカソン powered by ProjectLINKS

https://topaz.dev/projects/rf23wuwzyssmxsjj

国土交通省 Project LINKS のオープンデータ(CSV)から、縦スクロールのショート動画を作り、視聴といいねから好みを学習して次の動画を選ぶ Web アプリです。

## 構成

| ディレクトリ | 役割 | 言語 |
| --- | --- | --- |
| `apps/web` | 画面と BFF(DB の読み書きはすべてここ) | TypeScript(Next.js) |
| `services/recsys` | 好みのベクトルの計算(状態を持たない内部サービス) | Rust |
| `pipeline` | Batch。CSV から動画データを作り、DB に公開する | Python |
| `packages/shared` | pipeline と web の契約(シーンJSONの JSON Schema) | JSON Schema |
| `datasets` | データセット別の列定義 YAML | YAML |
| `docs` | 設計書、データ定義書、決定の記録(ADR) | - |

## セットアップ

### 前提

- macOS
- [Homebrew](https://brew.sh/)
- Docker(DB の起動に使う。Docker Desktop など、`docker compose` が使えるもの)

次のツールは、すべて mise が `mise.toml` のバージョンで入れます。個別にインストールする必要はありません(バージョンは `mise.toml` が正です)。

| 用途 | ツール |
| --- | --- |
| web | Node.js、pnpm |
| recsys | Rust(clippy、rustfmt を含む) |
| pipeline | Python、uv |
| DB | dbmate(マイグレーション。DB 本体は Docker で起動する) |
| 開発補助 | lefthook(git hook)、Terraform(インフラを触るときだけ) |

### 1. mise を入れて有効にする

```bash
brew install mise
```

```bash
echo 'eval "$(mise activate zsh)"' >> ~/.zshrc
```

```bash
source ~/.zshrc
```

### 2. ツールと依存を入れる

リポジトリのディレクトリで実行します。

```bash
mise trust
```

```bash
mise install
```

```bash
mise run setup
```

`mise run setup` は次をまとめて行います。

- `.env.example` をコピーして `.env.local` を作る(すでにあれば何もしない)
- web(pnpm)、pipeline(uv)、recsys(cargo)の依存を入れる
- git hook(lefthook)を登録する

### 3. 確認する

```bash
mise doctor
```

`activated: yes` と `No problems found` が出れば準備完了です。

## 起動

先に DB を起動します(初回はイメージの取得に少し時間がかかります)。

```bash
mise run db-up
```

PostgreSQL 16 + pgvector を Docker で起動し、`db/migrations` のマイグレーションを流します。続けて、web と recsys を起動します。

```bash
mise run dev
```

web と recsys がまとめて起動します。個別に起動するときは `mise run web` / `mise run recsys` を使います。

| サービス | URL | 確認用のエンドポイント |
| --- | --- | --- |
| web | http://localhost:3000 | `GET /api/health`(DB に接続できれば 200、できなければ 503)、`GET /api/health/recsys`(web から recsys に内部 HTTP でつながれば 200) |
| recsys | http://localhost:8080 | `GET /healthz`、`GET /internal/ping` `POST /internal/feed|taste|reload`(ヘッダー `X-Internal-Token` が必要) |
| DB | localhost:5432 | `mise run db-check`(pgvector が入っていることと、recsys のロールが読み取り専用であることを確かめる。要 `mise run db-up`)。`mise run db-psql` でつなげる |
| DB マイグレーション | (使い捨ての DB) | `mise run db-test`(空の DB に適用、2回流す、制約と recsys ロールの権限の確認。要 `mise run db-up`) |

起動できたかは、別のターミナルで次のとおり確認します。

```bash
curl -i http://localhost:3000/api/health
```

`HTTP/1.1 200` と `{"status":"ok","db":"ok"}` が返れば、web と DB がつながっています。続けて `curl -i http://localhost:3000/api/health/recsys` が 200 なら、web から recsys までつながっています。

終わったら、`mise run dev` を Ctrl+C で止め、`mise run db-down` で DB を止めます。

DB のタスクは次のとおりです。

| コマンド | 内容 |
| --- | --- |
| `mise run db-up` | DB を起動し、マイグレーションを流す |
| `mise run db-down` | DB を止める(データは残る) |
| `mise run db-reset` | データを消して作り直す |
| `mise run db-migrate` | 未適用のマイグレーションを流す |
| `mise run db-new 名前` | マイグレーションのファイルを作る(`db/migrations/`) |
| `mise run db-psql` | psql でつなぐ |
| `mise run db-check` | DB の状態を確かめる(`mise-tasks/db-check`。`mise.toml` ではなくファイルタスク) |
| `mise run db-test` | マイグレーションの検証(使い捨ての DB) |

recsys 用のロール(`db/init/01-roles.sql`)は、ボリュームを最初に作るときにしか作られません。ロールを足す前に作ったボリュームを使っている場合は、`mise run db-reset` で作り直してください。

### pipeline(Batch)

```bash
cd pipeline && uv run opendopa --help
```

サブコマンド(`profile`、`generate`、`embed`、`publish` など)の中身は、これから実装します。

#### publish のあとの recsys の再読み込み(Azure)

Azure の recsys は内部 ingress のみのため、手元 PC や CI の `publish` から `/internal/reload` は届かず、警告(`recsys の reload に失敗しました`)だけで終わる。公開のあとは、`az login` した状態で `make recsys-reload` を実行する。recsys が再起動し、起動時に新しい索引を読み込む。

## 開発

### テストの実行

```bash
mise run test
```

全言語のテストをまとめて流します。言語ごとに流すときは `mise run test:web` / `test:shared` / `test:pipeline` / `test:recsys` を使います(`mise run lint:*` も同じ並びです)。web は、変更したら `cd apps/web && mise exec -- pnpm typecheck` も通してください。テストは DB を必要としません。

`data/raw/` は git に入りません(`.gitignore` 対象)。実データ(オープンデータの CSV)を `data/raw/<データセットID>/` に置くと、実データを使うテストも走ります。ファイル名は `docs/data.md` の一覧のとおりで、例は `data/raw/accident/02_jikojyouhou.csv` です。worktree では `data/raw` が空なので、メインの `data/raw` へのシンボリックリンクを張ると実データで動かせます。

注意: 実データがあると、`pipeline/tests/test_generate.py::test_generate_accident_real` が main でも失敗します(推定秒数の最小 18.31 が期待の 19 未満)。CI は実データなしで skip するので影響しません。

### コマンド

| コマンド | 内容 |
| --- | --- |
| `mise tasks` | タスクの一覧 |
| `mise run lint` | 全言語の lint(CI と同じ内容。`.github/workflows/ci.yml` が同じ内容を実行する) |
| `mise run test` | 全言語のテスト |
| `mise run fmt` | 全言語の整形 |
| `mise run gen-types` | `packages/shared/schema` から TS の型と pydantic のモデルを生成する |

- 環境変数は、ルートの `.env.local` に書きます。mise が自動で読み込み、すべてのアプリに渡します。どんな変数があるかは `.env.example` を見てください
- commit すると、lefthook が変更したファイルを整形します
- シーンJSONの形を変えるときは、`packages/shared/schema/*.json` を直してから `mise run gen-types` を実行します。生成されたファイルは手で編集しません

## CI

PR と `main` への push で、GitHub Actions(`.github/workflows/ci.yml`)が検証を行います。シークレットは使いません。

| ジョブ | 内容 | 走る条件(変更があったとき) |
| --- | --- | --- |
| `web` | `pnpm lint && pnpm test`、`pnpm typecheck` | `apps/web`、`packages/shared`、pnpm の設定 |
| `pipeline` | `ruff format --check`、`ruff check`、`uv run pytest` | `pipeline`、`packages/shared/schema`、`datasets` |
| `recsys` | `cargo fmt --check`、`cargo clippy`、`cargo test` | `services/recsys` |
| `types` | 生成した型が JSON Schema と一致しているか(`mise run gen-types:check`) | `packages/shared`、`pipeline` の依存 |
| `infra` | `terraform fmt -check`、`terraform validate`(`mise run lint:infra`。Azure には接続しない) | `infra` |
| `ci-ok` | 上のジョブの結果をまとめる(常に走る) | 常に |

`mise.toml` と `ci.yml` を変えたときは、すべてのジョブが走ります。ツールのバージョンは `mise.toml` が正で、キャッシュは pnpm のストア、uv、cargo(`target/`)に効いています。

### 必須チェックの設定手順

リポジトリの管理者が一度だけ設定します。

1. GitHub のリポジトリで **Settings → Rules → Rulesets**(または **Settings → Branches → Branch protection rules**)を開く
2. `main` を対象に、新しいルールを作る
3. **Require status checks to pass** を有効にし、チェックに **`CI(必須チェック)`**(ジョブ `ci-ok`)だけを追加する
4. 必要なら **Require a pull request before merging** も有効にして保存する

`web` などのジョブを個別に必須にしないでください。パスフィルタでスキップされたジョブは必須チェックを満たせず、PR が止まるおそれがあります。`ci-ok` は、スキップを成功として扱い、失敗・キャンセルだけを落とします。なお、チェックを追加できるのは、一度 PR で走ったあとです。

## CD(デプロイ)とインフラ変更

Azure への認証は OIDC(フェデレーション資格情報)です。クライアントシークレットなど、Azure の長期の資格情報は GitHub に置きません(ADR-0019)。

| ワークフロー | きっかけ | 内容 |
| --- | --- | --- |
| `.github/workflows/deploy.yml` | `main` の CI が成功したあと(手動実行も可) | web と recsys のイメージをビルド → Container Registry に push → Container Apps を更新 → `/api/health` を確認 |
| `.github/workflows/infra.yml` | 手動実行(`workflow_dispatch`) | `terraform plan`(要約に出る)→ environment `infra-apply` の承認 → `terraform apply`(承認した plan をそのまま適用) |

変数(`AZURE_CLIENT_ID_DEPLOY` / `AZURE_CLIENT_ID_INFRA`)が空のあいだ、これらは何もせず終わります。下の設定を人が行ってから動きます。**以下はすべて Azure の課金とアクセス権に関わるため、人が実行します。**

### 1. Azure 側(最初の1回)

前提: `az login` 済み、Terraform の state 用 Storage(`infra/bootstrap/bootstrap.sh`)と、`mise run infra-apply` による最初のインフラ作成が済んでいること。以下の `<...>` は自分の値に置き換えます。

アプリ登録は 2 つ作ります(権限を分けるため)。

| アプリ登録 | 使う場面 | ロール |
| --- | --- | --- |
| `opendopa-gh-deploy` | `deploy.yml` | Container Registry に `AcrPush`、リソースグループ `rg-opendopa-<env>` に `Container Apps Contributor`(イメージの更新に必要な最小の権限) |
| `opendopa-gh-infra` | `infra.yml` | サブスクリプションに `Contributor` と `Role Based Access Control Administrator`(Terraform が `AcrPull` の割り当てを作るため)、state の Storage Account に `Storage Blob Data Contributor` |

```bash
# 例: deploy 用(infra 用も同じ要領で名前とロールを変える)
APP_ID=$(az ad app create --display-name opendopa-gh-deploy --query appId -o tsv)
az ad sp create --id "$APP_ID"
# フェデレーション資格情報: environment dev の実行だけを信頼する
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "gh-env-dev",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:proto08/opendopa:environment:dev",
  "audiences": ["api://AzureADTokenExchange"]
}'
SP_ID=$(az ad sp show --id "$APP_ID" --query id -o tsv)
az role assignment create --assignee-object-id "$SP_ID" --assignee-principal-type ServicePrincipal \
  --role AcrPush --scope "$(az acr show -n <ACR名> --query id -o tsv)"
az role assignment create --assignee-object-id "$SP_ID" --assignee-principal-type ServicePrincipal \
  --role "Container Apps Contributor" --scope "$(az group show -n rg-opendopa-<env> --query id -o tsv)"
```

`opendopa-gh-infra` のフェデレーション資格情報の subject は 2 つ(`repo:proto08/opendopa:environment:infra-plan` と `repo:proto08/opendopa:environment:infra-apply`)です。

### 2. GitHub 側

**Settings → Environments** で次の 3 つを作ります。

| environment | 用途 | 設定 |
| --- | --- | --- |
| `dev` | deploy | 承認なし(必要なら Deployment branches を `main` に限定する) |
| `infra-plan` | plan | 承認なし |
| `infra-apply` | apply | **Required reviewers** に承認者を入れる。Deployment branches を `main` に限定する |

**Settings → Secrets and variables → Actions → Variables** に次を登録します(値は秘密ではありません)。

| 変数 | 値 |
| --- | --- |
| `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` | テナント ID / サブスクリプション ID |
| `AZURE_CLIENT_ID_DEPLOY` / `AZURE_CLIENT_ID_INFRA` | 上の 2 つのアプリ登録のクライアント ID |
| `AZURE_RESOURCE_GROUP` / `ACR_NAME` / `WEB_APP_NAME` / `RECSYS_APP_NAME` | `terraform output` の `resource_group_name` / `registry_name` / `web_app_name` / `recsys_app_name` |
| `TF_ENV_NAME` / `TF_NAME_SUFFIX` | `terraform.tfvars` の `env_name` / `name_suffix`(suffix なしなら空) |
| `TFSTATE_RESOURCE_GROUP` / `TFSTATE_STORAGE_ACCOUNT` | `infra/backend.hcl` の `resource_group_name` / `storage_account_name` |

**Secrets** には、アプリの設定値だけを、`infra-plan` と `infra-apply` の両方の environment secrets として登録します(Azure の資格情報ではありません)。

| Secret | 内容 |
| --- | --- |
| `TF_POSTGRES_ADMIN_PASSWORD` | `TF_VAR_postgres_admin_password` と同じ値(16 文字以上) |
| `TF_INTERNAL_TOKEN` | `TF_VAR_internal_token` と同じ値(16 文字以上) |
| `TF_RECSYS_DATABASE_URL` | `TF_VAR_recsys_database_url`(読み取り専用ロールを作る前は空) |
| `TF_PLAN_PASSPHRASE` | plan ファイル(artifact)を暗号化・復号するパスフレーズ。長いランダム文字列を、`infra-plan` と `infra-apply` の両方に**同じ値**で登録する。plan ファイルには DB パスワードなどが入り、このリポジトリは public で artifact を誰でも取得できるため、暗号化して渡す |

### 3. 使い方

- デプロイ: `main` に merge すると、CI が通ったあとに `Deploy` が走ります。手動で再デプロイするときは Actions の `Deploy` から **Run workflow** します。
- インフラ変更: Actions の `Infra` から **Run workflow** → `plan` の要約を確認 → `infra-apply` の承認 → `apply`。
- 最小構成から始める(無料試用など): 必須は Resource Group、Container Registry、Log Analytics、Postgres、Container Apps で、Azure OpenAI(`enable_openai`)、Blob(`enable_storage`)、Front Door(`enable_cdn`)は `terraform.tfvars` で `false` にできます(既定は `true`。`enable_openai = false` のときは `AZURE_OPENAI_*` が空になります)。変数は `.env.example` の `TF_VAR_*` と `infra/terraform.tfvars.example` を参照してください。

## Azure 環境をゼロから作る・消す

新しい `env_name` で、Azure 環境を最初から作る手順です。**Azure の課金とアクセス権に関わるため、人が実行します**(自動化したワークフローでは行いません)。CI/CD の初期設定(OIDC・GitHub の変数)は前節の「CD(デプロイ)とインフラ変更」のとおりです。

前提: `az login` 済み(サブスクリプションで Owner か、Contributor と User Access Administrator)、`docker`、`terraform`(または `TF=tofu`)、`dbmate`(`mise install` で入る)。

### 作る

```bash
# 1. state 用の Storage を作る(最初の1回だけ。infra/backend.hcl が書かれる)
TFSTATE_SUFFIX=ab12 ENV_NAME=demo ./infra/bootstrap/bootstrap.sh

# 2. 設定を用意する(terraform.tfvars はコミットしない)
cp infra/terraform.tfvars.example infra/terraform.tfvars   # env_name を新しい名前にする
export TF_VAR_postgres_admin_password='...'                # 16 文字以上
export TF_VAR_internal_token='...'                         # 16 文字以上

# 3. インフラを作る
make infra-init && make infra-plan && make infra-apply

# 4. DB のマイグレーションを流す(Postgres は Azure 内サービスからのみ許可のため、手元から流すときは一時的にファイアウォール規則を足す)
#    DATABASE_URL は `terraform -chdir=infra output -raw database_url`
DATABASE_URL="$(terraform -chdir=infra output -raw database_url)" dbmate up

# 5. イメージをビルドして Container Apps を更新する
make deploy
```

### 確認する

```bash
WEB_URL="$(terraform -chdir=infra output -raw web_url)"

# /api/health が 200(DB 接続を含む。DB に繋がらなければ 503)
curl -fsS -o /dev/null -w '%{http_code}\n' "$WEB_URL/api/health"

# recsys が外部から届かない(内部 ingress のみ)。名前解決できない、または接続できないことを確かめる
RECSYS_FQDN="$(terraform -chdir=infra output -raw recsys_internal_url | sed 's#^https\?://##')"
curl -sS --max-time 10 "https://$RECSYS_FQDN/healthz" || echo "届かない(期待どおり)"
```

`/api/health/recsys` は web から recsys への到達を確認します。recsys に索引を読ませるには、pipeline の `publish` のあとに `make recsys-reload` を実行します(前述)。

### 消す

```bash
terraform -chdir=infra destroy        # 作った環境を消す。確認の入力が要る
# state 用の Storage(rg-opendopa-tfstate)は別に作ったものなので、不要なら人が az group delete で消す
```

`destroy` はデータ(DB・Blob)も消します。残したいデータがあれば、先に取り出してください。Front Door と Postgres は課金が続くので、使い終わったら消します。

## ドキュメント

- [設計書](docs/design_doc.md)
- [データ定義書](docs/data.md)
- [決定の記録](docs/DECISIONS.md)(ADR の索引を兼ねる)
- [CLAUDE.md](CLAUDE.md): Claude Code 向けの案内
