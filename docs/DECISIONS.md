# 決定の記録

設計書(`docs/design_doc.md`)の既定値から外れた判断や、実装中に決めたことを記録する。

- Issue 単位で決めた大きな判断は、`docs/adr/NNNN-*.md`(NNNN は Issue 番号)に、理由とともに書く。
- 実装中に決めた小さなことは、下の「小さな決定」に1行で書く(日付、決定、理由)。

## ADR の一覧

| ADR | 題 | Issue |
| --- | --- | --- |
| [ADR-0012](adr/0012-repo-scaffold.md) | リポジトリの雛形(ツール、言語の境界、ハーネス) | #12 |
| [ADR-0013](adr/0013-docker-compose-and-migrations.md) | 環境構築(docker-compose と DB マイグレーション) | #13 |
| [ADR-0016](adr/0016-terraform-foundation.md) | Terraform の土台と基盤リソース | #16 |
| [ADR-0030](adr/0030-pipeline-ingest-stats.md) | パイプライン: 取り込み・クリーニング・derived・stats・fmt | #30 |

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
- 2026-11-04: Terraform の `terraform.tfvars`・`backend.hcl`・`tfplan`・state は .gitignore に入れ、`.terraform.lock.hcl` はコミットする。理由: 秘密・環境差分を入れず、プロバイダーのハッシュは全員で揃えるため(ADR-0016)。
- 2026-11-04: bootstrap.sh のロール割り当ては、既存確認のうえ失敗時は止め、container create は反映待ちとして最大12回リトライする。TFSTATE_SUFFIX は4〜7文字(接頭辞17文字+24文字上限)。理由: レビュー指摘で失敗の握りつぶしと文言の不一致を解消(ADR-0016)。実機未確認。
- 2026-11-04: `db/migrations` には、拡張(`vector`)、設計書 §5 の全テーブル、recsys ロールへの権限付与の3本を置く。理由: 受け入れ条件の「recsys 用の読み取り専用ロール」を確かめるにはテーブルが要り、§5 は確定しているため(ADR-0013 A2, A3)。
- 2026-11-04: `docker-compose.yml` の DB は `127.0.0.1` にだけ公開する。理由: ローカル用の弱いパスワードを、同じネットワークの他の端末に見せないため。
- 2026-11-04: 設計書・Issue の `make db-up` / `make dev` は `mise run db-up` / `mise run dev` と読み替える(ADR-0012 A9)。
- 2026-11-04: 穴・式の列名の検査は、列名が分かる `validate_against_columns(def, columns)` で行う。`load_dataset` は `derived`/`stats` に無い穴を通し、`columns` を渡したときだけ続けて検査する。理由: 列名は CSV を読むまで分からず、読み込み時に `{foo}` と列名を区別できない(#29 のタスクの分担どおり。イシューのテスト項目「読み込み時エラー」は、`load_dataset(path, columns=...)` で満たす)。
- 2026-11-04: 列定義 YAML のモデルは、未知のキーをエラーにする(`derived` と `stats` の項目だけ、`op` ごとの引数(#30)のため余分なキーを残す)。理由: キーの打ち間違いを読み込み時に見つけるため。
- 2026-11-04: 式の比較は、`null` との大小・型違いの大小を偽にし、行にない列は `null` として扱う。型の数が4〜6から外れるときは `UserWarning`(エラーにしない)。理由: 式は実行時に例外を出さず、データの欠損で動画が落ちないようにするため。
- 2026-11-04: 式の列名は `\w+` に限る。`No.` のようにドットを含む列は式に書けないので、`rename` で置き換える(穴 `{No.}` には使える)。理由: `a.b`(属性参照)を拒否する仕様のため。
- 2026-11-04: `template_select.decision` の存在検査は `decisions` が空でも行う(空なら必ずエラー)。一方 `decisions[].fallback.rule` が `fallback_rules` にあるかは検査しない。理由: `regex_pii` のように、`fallback_rules` ではなく正規表現の組み込みルールを指す名前が docs/data.md にあるため(#29 レビュー対応)。
- 2026-11-04: CI は `.github/workflows/ci.yml` の1ファイルにし、変更の検出(dorny/paths-filter)→ 部分ごとのジョブ → 結果をまとめる `ci-ok` の形にする。必須チェックには `ci-ok` だけを指定する。理由: パスフィルタでスキップされたジョブを個別に必須にすると PR が止まるため(Issue #14)。
- 2026-11-04: CI のツールは `jdx/mise-action` で `mise.toml` のバージョンを使い、ジョブごとに必要なものだけ入れる。キャッシュは pnpm のストアと uv が `actions/cache`、cargo が `Swatinem/rust-cache`。理由: ローカルと CI のバージョンを一致させ、不要な Rust などを入れる時間を省く。
- 2026-11-04: Issue の列挙に加えて、web の `pnpm typecheck`、pipeline の ruff、`gen-types:check` も CI で検査する。理由: CLAUDE.md の完了条件と設計書 §12.4(生成した型の差分の検査)に合わせるため。イメージのビルドとデプロイは対象外(検証のみ)。
- 2026-11-04: CI の `concurrency` は PR のときだけ古い実行を止め(`cancel-in-progress: ${{ github.event_name == 'pull_request' }}`)、main への push では止めない。理由: 連続マージ時に、先のマージ commit の検証が途中で消えるのを避けるため(PR #68 のレビュー対応)。
- 2026-11-04: シーンJSONの検証は、TS が ajv(`ajv/dist/2020`)、Python が jsonschema(Draft 2020-12)で、どちらも `packages/shared/schema/scene.schema.json` を直接読む。pipeline のパスは `packages/shared` をリポジトリ内の相対位置で解決する。理由: 契約は JSON Schema が正(ADR-0012 A2)で、どちらの言語も同じファイルを読めば、フィクスチャの合否が一致する。生成した pydantic モデルは型として使い、検証の判定には使わない。
- 2026-11-04: サンプルの置き場を `packages/shared/examples/` から `fixtures/` に変え、`accident-0001.json`(`map: null`)と `map-route` / `map-polygon` / `map-points` の4本にした。理由: #28 の指定。テストが4本すべての検証を通ることを確かめる。`@opendopa/shared/fixtures/*` で web からも読める。
- 2026-11-04: `packages/shared` に `tsconfig.json` と `typecheck`(`tsc --noEmit`)を足し、`mise run lint` の `lint:shared` に入れた。eslint は足さない。理由: vitest は型を検査せず、shared の型エラーが lint・テストをすり抜けていた(実際に `@types/node` 不足が見つかった)。eslint は規則を決める必要があり、CI(#14)で扱う方が自然。
- 2026-11-04: `mise run test` に `test:shared`(ajv の検証テスト)を足した。理由: 言語の境目のテストを CI と同じ入口で流すため。
- 2026-11-04: 大きな数字の文字サイズは、最終的な値の桁数(区切りと小数点を除く)で決める: 4桁まで 21cqw、5桁 17、6桁 14、7桁 12.5、8桁以上 11.5(最小)。カウント中に大きさが変わらないよう、途中の値ではなく最終の値で決める。理由: #43 に「モックはなく、具体的な分岐は実装時に決める」とあり、日本語の 1 桁をステージ幅の約 1 文字分とみて、8 桁までが幅 100cqw に収まるようにした(ブラウザで実測はしていない)。
- 2026-11-04: 再生の時計は DOM と React に依存しない `ScenePlayer`(`lib/scenePlayer.ts`)に置き、`useScenePlayer` は `useSyncExternalStore` で繋ぐだけにした。時計は requestAnimationFrame で進め、1 回の更新で進める上限を 0.25 秒とする。理由: fake timers でテストできる形にする(#43)。裏タブで時計が飛んでも、字幕と音声が一気にずれない。
- 2026-11-04: 一時停止アイコンは、切り替えのたびに出す(一時停止は停止の印、再開は再生の印)。`prefers-reduced-motion` では動かさず、一時停止中だけ出す。理由: 仕様は「アイコンの動きを止める」のみで、動きなしだと出しっぱなしになるため、状態を表す表示にした。
- 2026-11-04: `/dev/stage` は `NODE_ENV === "production"` で `notFound()`(本番ビルドで 404 を確認)。フィクスチャは countUp がすべて false なので、数字の上書きと countUp の切り替えを画面に付けた。
- 2026-11-04: ステージの CSS は `components/stage.css`(Stage から読み込む)、色・書体・動きのトークンは `app/globals.css` の `:root` に置く。フォントは `next/font/google` で CSS 変数(`--font-dela`、`--font-noto`)にする。
- 2026-11-04: pipeline に pandas を使う。理由: イシュー #30 のテストが「小さな DataFrame」で書かれており、グループごとの集計(stats)が書きやすいため。
- 2026-11-04: CSV はすべて文字列で読み、欠損以外がすべて数の形の列だけ数値にする。先頭が 0 の符号(`01100` など)は文字列のまま。理由: 行政区域コードの 0 を落とさないため(ADR-0030)。
- 2026-11-04: `extract_pref` は、47 都道府県の名前を列挙して先頭一致で取る(`...県` の正規表現にしない)。理由: 3 文字の県や「北海道」、海外の長い文を誤って取らないため。事故データの「194 行中 3 行は取れない」を満たす想定(データがあるときのテストで確認)。
- 2026-11-04: `sentence` は `。` `！` `？`(と直後の閉じ括弧)で切り、元の文字を変えない。`map`・`classify` の `else` に当たるのは、元の値が欠損でない行だけ(`classify` だけは欠損も `else`)。理由: 欠損の行に「負傷者の報告があります」のような文を作らないため。
- 2026-11-04: stat の `fmt:` を書くと `<name>_text` の列を作り、穴で使える(`DatasetDef.defined_names` に含める)。derived の数字の表記は `op: format` で行い、`numbers` には残さない(元の列の値が行にあるため、照合は元の行の値で行える)。理由: 原稿の数字をすべて `fmt` に通すため。
- 2026-11-04: `rules` プロバイダーは `confidence=1.0`、`used_fallback=False` とし、フォールバックの割合に数えない。理由: `rules` は「判断モデルの代わりに使うと選んだ既定」で、`used_fallback` は判断モデルが低確信度・失敗だったことを示すため。判断モデルが失敗して `rules` に戻ったときは `provider="rules"`、`used_fallback=True` で記録する(#32)。
- 2026-11-04: `rules` の `noul` は常に `regex_pii`(電話番号・メール・番地らしい文字列)で判定し、確率は 0 か 1。`choice` は、規則の結果が選択肢(その行で埋められる型)にないとき `default`、それもなければ先頭の選択肢にする。理由: 埋められない型は選ばれない約束のため(#32)。
- 2026-11-04: フォールバックの規則は `state` の列だけで評価し、規則が `state` にない列を参照していたらエンジンの初期化時にエラーにする。`rules` プロバイダーは質問文で判断を引くため、質問文は判断ごとに別にする。理由: `rules` とフォールバックの結果を一致させ、判断モデルと同じ入力だけで決まるようにするため(#32)。
- 2026-11-04: 判断モデルのフォールバックが `noul` で、`fallback` が `regex_pii` でない(または無い)ときは、安全側に倒して確率 1.0(個人情報あり)とする。理由: 安全チェックの失敗で、個人情報を含む行を通さないため(#32)。
- 2026-11-04: キャッシュには判断モデルの生の結果だけを入れ、エラー・タイムアウトは入れない。`min_confidence` によるフォールバックは読み出し後に毎回判定する。理由: しきい値を変えても再計算せず、一時的な失敗を固定しないため。キーは `(provider, kind, 質問, state, 選択肢の id と label, rubric)` の SHA-256。1問のタイムアウトは30秒(スレッドで待つだけで、止まらない処理は放置する)(#32)。
- 2026-11-04: エンジンは `decisions` の順に、同じ判断の問いをまとめて処理する。プロバイダーが `decide_batch` を持てばそれで一括推論し(失敗したら1件ずつに戻す)、なければ `decide` を1件ずつ呼ぶ。同じ入力は1回だけ推論する。`decisions_report.json` はエンジンの `write_report` で出し、書き出し先(`out/<id>/`)の決定と CLI への接続は `decide`/`generate` コマンド側(#35 など)で行う(#32)。
- 2026-11-04: Decider のキャッシュで、壊れた行(途中で切れた行など)は読み飛ばし、その問いは次回に推論し直す。理由: 追記式なので実行中に落ちると最終行が切れる。キャッシュは作り直せるので、パイプラインを止めない。
- 2026-11-05: AI の作業状況は、ラベル `status::*` を正にして GitHub Projects の Status に Actions で同期し、Board で見る(`docs/kanban.md`、`.github/workflows/project-status.yml`)。理由: ラベルは `gh` で書きやすく一覧でも見える。Board の列にできるのは Status 項目だけなので、同期をワークフローに任せてスキルを軽くするため。`PROJECT_NUMBER` と `PROJECT_TOKEN` が未設定の間、ワークフローは何もしない。
- 2026-11-05: Dependabot を入れ(`.github/dependabot.yml`)、minor・patch はまとめて CI(必須チェック `ci-ok`)が通れば自動でマージし、major は個別のPRにして人が見る(`.github/workflows/dependabot-automerge.yml`)。対象は npm(ルート)・uv(`pipeline`)・cargo(`services/recsys`)・github-actions・terraform(`infra`。CI に検証がないので PR は作るが自動マージはしない)。docker-compose のイメージ(pgvector)は ADR-0013 でバージョンを固定しているので対象外。週1回、cooldown 3日。マージ方法は履歴の形式に合わせて `--merge`。理由: 依存の更新を溜めず、major だけ人が見るため。自動マージの予約には、リポジトリの設定(Allow auto-merge を ON、main の保護で `ci-ok` を必須チェックにする)が前提で、コードでは設定できない。`mise.toml` のツールのバージョンは Dependabot の対象外。
