# 決定の記録

設計書(`docs/design_doc.md`)の既定値から外れた判断や、実装中に決めたことを記録する。

- Issue 単位で決めた大きな判断は、`docs/adr/NNNN-*.md`(NNNN は Issue 番号)に、理由とともに書く。
- 実装中に決めた小さなことは、下の「小さな決定」に1行で書く(日付、決定、理由)。

## ADR の一覧

| ADR | 題 | Issue |
| --- | --- | --- |
| [ADR-0012](adr/0012-repo-scaffold.md) | リポジトリの雛形(ツール、言語の境界、ハーネス) | #12 |

## 小さな決定

- 2026-11-02: Devcontainer は使わず、mise だけで環境をそろえる。理由: チーム全員が Mac で、mise でツールが一通りそろう。必要になれば、同じ `mise.toml` を使って後から足せる(ADR-0012 A3)。
- 2026-11-02: 型の生成ツールは、TS が json-schema-to-typescript、Python が datamodel-code-generator(pydantic v2、ruff で整形)。理由: どちらも JSON Schema から直接生成でき、出力が決定的(ADR-0012 A13 の差分検査が成り立つ)。
- 2026-11-02: シーンJSONの型名は、JS・DOM の標準の型と重ならないように `SceneMap`(地図)、`FlowComment`(流れるコメント)とする。`numbers`(検証用の記録)の形は M1 で決めるまで任意の配列にしておく。
- 2026-11-02: pipeline は設計書 §4.2 の配置(`pipeline/opendopa_pipeline/`)に合わせ、`src/` を使わない(uv_build の `module-root = ""`)。
- 2026-11-02: web の `/api/health` は `connection()` を呼んで、リクエストのたびに実行する。理由: Next.js 16 の Cache Components では、条件次第で `GET` の Route Handler がビルド時に事前生成されるため。
- 2026-11-04: CI は `.github/workflows/ci.yml` の1ファイルにし、変更の検出(dorny/paths-filter)→ 部分ごとのジョブ → 結果をまとめる `ci-ok` の形にする。必須チェックには `ci-ok` だけを指定する。理由: パスフィルタでスキップされたジョブを個別に必須にすると PR が止まるため(Issue #14)。
- 2026-11-04: CI のツールは `jdx/mise-action` で `mise.toml` のバージョンを使い、ジョブごとに必要なものだけ入れる。キャッシュは pnpm のストアと uv が `actions/cache`、cargo が `Swatinem/rust-cache`。理由: ローカルと CI のバージョンを一致させ、不要な Rust などを入れる時間を省く。
- 2026-11-04: Issue の列挙に加えて、web の `pnpm typecheck`、pipeline の ruff、`gen-types:check` も CI で検査する。理由: CLAUDE.md の完了条件と設計書 §12.4(生成した型の差分の検査)に合わせるため。イメージのビルドとデプロイは対象外(検証のみ)。
