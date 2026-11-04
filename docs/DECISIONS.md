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
- 2026-11-04: シーンJSONの検証は、TS が ajv(`ajv/dist/2020`)、Python が jsonschema(Draft 2020-12)で、どちらも `packages/shared/schema/scene.schema.json` を直接読む。pipeline のパスは `packages/shared` をリポジトリ内の相対位置で解決する。理由: 契約は JSON Schema が正(ADR-0012 A2)で、どちらの言語も同じファイルを読めば、フィクスチャの合否が一致する。生成した pydantic モデルは型として使い、検証の判定には使わない。
- 2026-11-04: サンプルの置き場を `packages/shared/examples/` から `fixtures/` に変え、`accident-0001.json`(`map: null`)と `map-route` / `map-polygon` / `map-points` の4本にした。理由: #28 の指定。テストが4本すべての検証を通ることを確かめる。`@opendopa/shared/fixtures/*` で web からも読める。
- 2026-11-04: `packages/shared` に `tsconfig.json` と `typecheck`(`tsc --noEmit`)を足し、`mise run lint` の `lint:shared` に入れた。eslint は足さない。理由: vitest は型を検査せず、shared の型エラーが lint・テストをすり抜けていた(実際に `@types/node` 不足が見つかった)。eslint は規則を決める必要があり、CI(#14)で扱う方が自然。
- 2026-11-04: `mise run test` に `test:shared`(ajv の検証テスト)を足した。理由: 言語の境目のテストを CI と同じ入口で流すため。
