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
- 2026-11-04: recsys の設定ファイルは TOML(`services/recsys/config/recsys.toml`、キーは小文字スネークケース)。書かない項目は既定値、未知のキーと範囲外の値(`tau<=0` など)はエラー。理由: 綴りの誤りや 0 除算を起動時に気づくため。recsys-core の依存は serde と toml(parse のみ)に限る(#39)。
- 2026-11-04: いいねは、動画ごとに「最後の `like` の位置」で 1 回だけ適用し、そこが `liked=false` なら適用しない。それ以前の `like` は無視。理由: 設計書 §7.3「最後のイベントが liked=true のときだけ有効」を、再生の順序(その後の view の影響)も含めて一意にするため(#39)。
- 2026-11-04: 索引にない `videoId` や `ratio` が数でないイベントは無視し、`replay_with_report` が `skipped` に理由を返す(警告は呼び出し側の recsys-server が出す)。ゼロベクトルになる更新は `u` を変えない。理由: recsys-core にログ用の依存を足さないため(#39)。
- 2026-11-04: `Index::new` は同じ ID の動画を、先のものを残して後ろを無視する(重複をエラーにしない)。埋め込みの次元がそろっていないことは `debug_assert` で検出する(`step` も同様)。理由: 索引は DB から読むだけで、重複や次元違いは読み込み側(#41)の不具合なので、起動を止めずに開発中に気づければ足りる(#39 のレビュー対応)。
