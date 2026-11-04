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
- Docker(DB の起動に使う。#13 で追加予定)

Node・pnpm・Python・uv・Rust・dbmate・lefthook は、すべて mise で入れます。個別にインストールする必要はありません。

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

```bash
mise run dev
```

web と recsys がまとめて起動します。個別に起動するときは `mise run web` / `mise run recsys` を使います。

| サービス | URL | 確認用のエンドポイント |
| --- | --- | --- |
| web | http://localhost:3000 | `GET /api/health`(DB に接続できれば 200、できなければ 503) |
| recsys | http://localhost:8080 | `GET /healthz` |

DB(PostgreSQL + pgvector)の起動とマイグレーションは #13 で追加予定です。それまでは `/api/health` は 503 を返します。

### pipeline(Batch)

```bash
cd pipeline && uv run opendopa --help
```

サブコマンド(`profile`、`generate`、`embed`、`publish` など)の中身は、これから実装します。

## 開発

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
