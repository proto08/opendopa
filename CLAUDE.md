# OpenDopa

国土交通省のオープンデータ(CSV)から、縦スクロールのショート動画(シーンJSON + 音声)を作り、視聴といいねから好みを学習して次の動画を選ぶ Web アプリ。ハッカソン(2026-11-07〜08)で動くものを作る。

## 最初に読むもの

- `docs/design_doc.md`: 設計書。§0.2「実装の約束」は必ず守る
- `docs/data.md`: CSV の列定義・テンプレート・データセット別の定義(pipeline を触るとき)
- `docs/adr/`: Issue 単位で決めたこと。`docs/decisions/`: 小さな決定(1決定1ファイル)。一覧は `mise run decisions-index`(`docs/DECISIONS.md` は 2026-11-05 までの分)
- `apps/web/AGENTS.md`: Next.js は学習データと違う版(16.4)。web を触る前に読む

## 構成と境界

| 場所 | 役割 | 言語 |
| --- | --- | --- |
| `apps/web` | 画面と BFF。**DB の読み書きはすべてここ** | TS(Next.js) |
| `services/recsys/recsys-core` | 好みのベクトルの計算(純粋な関数。HTTP・DB・tokio に依存させない) | Rust |
| `services/recsys/recsys-server` | 内部 API(axum)。**状態を持たず、DB には書き込まない**(起動時に読むだけ) | Rust |
| `pipeline` | Batch。CSV → 原稿 → シーンJSON → 埋め込み → DB への公開 | Python |
| `packages/shared/schema` | pipeline と web の契約(JSON Schema)。**これが正** | JSON |
| `db/migrations` | DB のマイグレーション(素の SQL。dbmate) | SQL |

- ベクトル計算は Rust だけで行う。Next.js で好みの更新や近傍検索を書かない
- 実行時(ユーザーが見ている最中)に LLM を呼ばない。原稿の数字は元データから機械的に作る
- シーンJSONの形を変えるときは `packages/shared/schema/*.json` を直して `mise run gen-types`。生成物(`packages/shared/src/generated/`、`pipeline/opendopa_pipeline/generated/`)は手で編集しない

## コマンド

ツールのバージョン・環境変数(`.env.local`)・タスクは `mise.toml` にまとまっている。一覧は `mise tasks`。

| コマンド | 内容 |
| --- | --- |
| `mise run setup` | 初回のセットアップ |
| `mise run dev` | web(:3000)と recsys(:8080)を起動 |
| `mise run lint` / `mise run test` | 全言語の lint / テスト(CI と同じ内容) |
| `mise run decisions-index` | ADR と小さな決定の索引を出す |
| `mise run fmt` | 全言語の整形 |
| `mise run gen-types` | JSON Schema から TS の型と pydantic のモデルを生成 |
| `mise exec -- uv run opendopa --help` | pipeline の CLI |

作業を終える前に `mise run lint` と `mise run test` を通す。web を変えたら `cd apps/web && mise exec -- pnpm typecheck` も通す。

## 決めたことの記録

- 設計書の既定値から外れた判断や、実装中に決めた小さなことは、`docs/decisions/YYYY-MM-DD-<slug>.md` に1決定1ファイルで書く(日付、決定、理由。形式は `docs/decisions/README.md`)。`docs/DECISIONS.md` には足さない(衝突するため)
- Issue 単位の大きな決定は `docs/adr/NNNN-*.md`(NNNN は Issue 番号)

## 書き方

- 文書・コメント・コミットメッセージは日本語
- `.env.local` は読まない・書かない(秘密の値が入る)。必要な変数は `.env.example` に足す
