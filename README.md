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
| recsys | http://localhost:8080 | `GET /healthz`、`GET /internal/ping`(ヘッダー `X-Internal-Token` が必要) |
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
| `ci-ok` | 上のジョブの結果をまとめる(常に走る) | 常に |

`mise.toml` と `ci.yml` を変えたときは、すべてのジョブが走ります。ツールのバージョンは `mise.toml` が正で、キャッシュは pnpm のストア、uv、cargo(`target/`)に効いています。

### 必須チェックの設定手順

リポジトリの管理者が一度だけ設定します。

1. GitHub のリポジトリで **Settings → Rules → Rulesets**(または **Settings → Branches → Branch protection rules**)を開く
2. `main` を対象に、新しいルールを作る
3. **Require status checks to pass** を有効にし、チェックに **`CI(必須チェック)`**(ジョブ `ci-ok`)だけを追加する
4. 必要なら **Require a pull request before merging** も有効にして保存する

`web` などのジョブを個別に必須にしないでください。パスフィルタでスキップされたジョブは必須チェックを満たせず、PR が止まるおそれがあります。`ci-ok` は、スキップを成功として扱い、失敗・キャンセルだけを落とします。なお、チェックを追加できるのは、一度 PR で走ったあとです。

## ドキュメント

- [設計書](docs/design_doc.md)
- [データ定義書](docs/data.md)
- [決定の記録](docs/DECISIONS.md)(ADR の索引を兼ねる)
- [CLAUDE.md](CLAUDE.md): Claude Code 向けの案内
