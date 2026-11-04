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
- 2026-11-04: 穴・式の列名の検査は、列名が分かる `validate_against_columns(def, columns)` で行う。`load_dataset` は `derived`/`stats` に無い穴を通し、`columns` を渡したときだけ続けて検査する。理由: 列名は CSV を読むまで分からず、読み込み時に `{foo}` と列名を区別できない(#29 のタスクの分担どおり。イシューのテスト項目「読み込み時エラー」は、`load_dataset(path, columns=...)` で満たす)。
- 2026-11-04: 列定義 YAML のモデルは、未知のキーをエラーにする(`derived` と `stats` の項目だけ、`op` ごとの引数(#30)のため余分なキーを残す)。理由: キーの打ち間違いを読み込み時に見つけるため。
- 2026-11-04: 式の比較は、`null` との大小・型違いの大小を偽にし、行にない列は `null` として扱う。型の数が4〜6から外れるときは `UserWarning`(エラーにしない)。理由: 式は実行時に例外を出さず、データの欠損で動画が落ちないようにするため。
- 2026-11-04: 式の列名は `\w+` に限る。`No.` のようにドットを含む列は式に書けないので、`rename` で置き換える(穴 `{No.}` には使える)。理由: `a.b`(属性参照)を拒否する仕様のため。
