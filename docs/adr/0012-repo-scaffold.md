# ADR-0012 リポジトリの雛形

- Issue: #12
- 日付: 2026-11-02
- 状態: 決定

## A1 マイグレーションの置き場所とツール

- 決定: `db/migrations/*.sql`(素の SQL)を dbmate で実行する。recsys では sqlx のコンパイル時の検査を使わない。
- 理由: DB には pipeline(Python)と web(TS)の両方が書き込むため、どちらの言語にも属させない。dbmate は1つのバイナリで動き、公式のイメージがあるので、ローカルでもデプロイ(Container Apps Job)でも同じ手順で流せる。recsys が DB を読むのは起動時の数本の SQL だけなので、コンパイル時の検査で得られるものが小さい。

## A2 `packages/shared` の位置づけ

- 決定: `packages/shared/schema/*.json`(JSON Schema)を正とし、TS の型と pydantic のモデルは、そこから生成する。
- 理由: シーンJSONは pipeline(Python)が作り、web(TS)が描画する。言語に依存しない形で契約を置くと、どちらかの言語の都合に引きずられない。

## A3 ツールのバージョン固定

- 決定: ルートの `mise.toml` で、Node・pnpm・Python・uv・Rust・dbmate のバージョンを固定する。
- 理由: 新しい環境でも `mise install` 1回でそろい、#15 の再現確認と #14 の CI で同じバージョンを使える。

## A4 JS 側の構成

- 決定: ルートに `pnpm-workspace.yaml` を置き、`apps/web` と `packages/shared` を workspace にする。web からは `@opendopa/shared` として import する。Turborepo などは使わない。
- 理由: A2 で生成した TS の型を、相対パスでなくパッケージとして読み込むため。JS のパッケージは2つだけなので、タスクを管理するツールは要らない。

## A5 lint とテスト

- 決定:
  - Rust: `cargo fmt`、`cargo clippy`、`cargo test`
  - Python: ruff(lint と整形)、pytest
  - TS: ESLint(Next.js 標準の設定)、Vitest
- 理由: 実装の大部分を AI エージェントが書くため、lint とテストを、変更が正しいかを判断する手段にする。道具は各言語の定番にそろえ、設定を最小にする。テストを厚くするのは、言語の境目(シーンJSONが JSON Schema に合うか)、recsys の疑似ユーザー(設計書 §14.2)、原稿の数字の一致(§14.3 の6)の3か所。

## A6 recsys の crate 構成

- 決定: `services/recsys` を Cargo workspace にし、`recsys-core`(計算の核。axum・sqlx などに依存しない)と `recsys-server`(axum による HTTP、sqlx による DB の読み込み、認証)の2つの crate に分ける。
- 理由: 設計書 §4.1 の「計算の核は、依存のないライブラリとして書く」を、約束事でなく依存関係で守らせる。核が HTTP や DB に触れるとビルドが落ちる。核だけを `cargo test` で速くテストでき、§14.2 の疑似ユーザーのテストも核の関数を呼ぶだけで書ける。

## A7 pipeline(Batch)の構成

- 決定: `uv init --package` で `pipeline/` を作り、`opendopa` コマンドを Typer で書く。`profile` / `generate` / `decide` / `embed` / `tts` / `publish` / `all` のサブコマンドを、中身が空の状態で置く。
- 理由: 設計書 §8.1 の `uv run opendopa ...` をそのまま使える。CLI は、手元でもコンテナ(将来の Container Apps Job など)でも同じ入口で呼べる。

## A8 環境変数の置き場所

- 決定: ルートの `.env.local` 1つにまとめ、`mise.toml` の `[env]`(`_.file = ".env.local"`)で読み込む。各アプリは環境変数を読むだけにする。`.env.example` をルートに置く。
- 理由: `INTERNAL_TOKEN` など、複数のアプリで同じ値を使うため。本番では Container Apps が環境変数を直接渡すので、ローカルと本番で同じコードが動く。
- 注意: 値が渡るのは、mise を有効にしたシェルか、`mise run` / `mise exec` を通したときだけ。

## A9 開発用コマンドの入口

- 決定: Makefile は作らず、`mise.toml` のタスク(`mise run dev`、`mise run db-up`、`mise run test` など)に統一する。`dev` は web・recsys を並列で起動し、個別に起動するタスクも用意する。長い処理は `mise-tasks/` にスクリプトとして置く。設計書と Issue の `make xxx` の表記は `mise run xxx` に書き換える。
- 理由: A3・A8 と合わせて、`mise.toml` 1つで「バージョン・環境変数・タスク」が決まる。環境変数が自動で渡り、並列での起動も書ける。エージェントには「`mise tasks` を見ればやれることが分かる」と伝えるだけで済む。

## A10 `/api/health` の扱い(#12 と #13 の分担)

- 決定: #12 では、`/api/health` が「DB に接続できなければ 503 を返す」ところまで作る。DB に接続して 200 が返ることの確認は、#13 の受け入れ条件にする。
- 理由: DB を立てるのは #13 なので、#12 だけでは 200 を確認できない。

## A11 `docs/DECISIONS.md` と ADR の使い分け

- 決定: Issue 単位の大きな決定は `docs/adr/NNNN-*.md`(NNNN は Issue 番号)に書く。実装中にエージェントが決めた小さなことは `docs/DECISIONS.md` に1行で書く。`DECISIONS.md` の先頭には ADR の一覧を置き、決定の索引にする。
- 理由: 設計書の「判断に迷ったら `docs/DECISIONS.md` に記録」という指示と矛盾させずに、理由まで残したい決定は ADR に分けるため。

## A12 バージョンの方針

- 決定: Node は最新の LTS、Rust は stable、Next.js・pnpm・uv は最新の安定版にする。Python は 3.13 にする。具体的な番号は、雛形を作るときに確かめて `mise.toml` に書く。
- 理由: ハッカソンの期間中はバージョンを上げないので、最初に最新をそろえる。Python だけは、umap-learn が依存する numba が最新の Python への対応に遅れることがあるため、一つ前にする。

## A13 JSON Schema から生成した型の扱い

- 決定: 生成した TS の型と pydantic のモデルを commit する。生成は `mise run gen-types` で行い、CI で生成し直して差分が出たら失敗にする。
- 理由: clone した直後から型が使え、PR で型の変更が読める。生成を忘れたときは CI が気づく。

## A14 #12 の段階での recsys の DB の扱い

- 決定: #12 の recsys は DB に接続しない。`/healthz` は `{"status":"ok","videos":0}` を返すだけにする。DB からの読み込みと、接続できないときの扱いは M4a で決める。
- 理由: 埋め込みを読む処理は M4a の範囲で、#12 で作ると、そのときに作り直すことになる。

## A15 ポート番号

- 決定: web は 3000、recsys は 8080(DB は #13 で 5432)。recsys は環境変数 `PORT` で変えられるようにする。ローカルの `RECSYS_URL` は `http://localhost:8080`。
- 理由: それぞれの標準的な番号にする。`PORT` は Container Apps でも使う。

## A16 Claude Code 向けのハーネス

- 決定: チーム全員が Claude Code を使うので、ハーネスは Claude Code にそろえる。#12 では次の3つを作る。
  - `CLAUDE.md`: 読むべき文書(設計書、`data.md`、`docs/adr/`、`docs/DECISIONS.md`)、`mise run` のタスク一覧、破ってはいけない境界(設計書 §0.2)
  - `.claude/settings.json`: よく使うコマンド(`mise run *` など)の許可
  - hooks: ファイルを編集するたびに、その言語の整形を自動でかける
- skills(`.claude/skills/`)は、繰り返す作業が見えてから追加する(例: M6 のデータセットの追加、ADR の作成)。
- 理由: エージェントが最初に読む場所に、文書・コマンド・境界をまとめる。skills は、実際の作業を一度やってから書いたほうが的確になる。

## A17 commit 前のチェック

- 決定: lefthook で、commit しようとしているファイルだけを対象に、整形と速い lint を並列で走らせる(`ruff`、`eslint`、`cargo fmt`)。整形したファイルは自動で commit に含め直す(`stage_fixed`)。`clippy`、テスト、生成した型の差分検査は CI(#14)に任せる。lefthook のバージョンは `mise.toml` で固定し、`lefthook install` は `mise run setup` に含める。
- 理由: CI があるので、pre-commit は数秒で終わる軽いチェックに絞る。lefthook は1つのバイナリで mise から入れられ、対象のファイルを絞る機能と並列実行が最初からある。Claude Code の hooks(A16)は編集した瞬間に整形し、lefthook は人が直接編集した分も含めて commit の前に止める。

## A18 `.env.example` に書く環境変数

- 決定: 設計書 §12.3 の環境変数をすべて書く。ローカルで使うもの(`DATABASE_URL`、`RECSYS_DATABASE_URL`、`RECSYS_URL`、`INTERNAL_TOKEN`、`MEDIA_BASE_URL`、`EMBED_DIM` など)には、そのまま動く値を入れる。Azure のキーなどは空欄にする。`*_PROVIDER` は Azure なしで動く値にする(`TTS_PROVIDER=none`、`DECIDER_PROVIDER=rules`、`LLM_PROVIDER=none`、`EMBED_PROVIDER=local`)。
- 理由: どんな環境変数があるかを一覧でき、Azure の資格情報がなくても clone した直後から動かせる。
