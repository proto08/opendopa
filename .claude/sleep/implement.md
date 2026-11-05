# sleep: 実装担当(イシューごと)

着手可能なイシュー1件を、worktree で実装し、self-review のうえ PR を作成する。既に自分のPRにレビューが付いているときは、指摘に対応する(レビュー対応モード)。

入力: イシュー番号、モード(通常 / レビュー対応)、レビュー対応なら PR 番号。原則(質問しない・他人のPRに投稿しない・破壊的操作をしない)は呼び出し元のプロンプトで渡される。

作業対象は自分の worktree だけ。メインの作業ディレクトリでは `git checkout` / `git switch` をしない。

## 手順

1. `gh issue view <番号>` で要求を把握する。不明点があっても質問せず、最も妥当な解釈で進め、解釈を PR 説明欄の「決めたこと」に書く。
2. worktree を作る。
   - **通常モード**: `git fetch origin` 後、`git worktree add -b <prefix>/<番号>-<description> ../opendopa-<番号> origin/<デフォルトブランチ>`。
     - `prefix` は `feat` / `fix` / `refactor` など、`description` は英小文字とハイフンの短い説明(例: `feat/18-add-login-api`)。
     - 同名の worktree・ブランチが既にある場合は、内容を確認し、未pushの変更がなければ再利用、あれば新しい名前(`-2` など)で作る。
     - 作る前に、イシューに `status::in-progress` を付ける。
   - **レビュー対応モード**: 新規ブランチは作らない。`git fetch origin <headRefName>` のあと、`git worktree add ../opendopa-<番号> <headRefName>`(ローカルブランチがなければ `-b <headRefName> origin/<headRefName>`)。PR を `status::fixing` にする(既存の `status::*` は同じコマンドで外す)。
     - 先に `origin/<デフォルトブランチ>` との差分を確認する。PR が `CONFLICTING` なら、`.claude/sleep/conflict.md` の手順 3〜4(merge。rebase・force push はしない)で解消してから指摘に対応する。解消できなければ、対応報告にその旨を書く。
3. 実装する(レビュー対応モードは、未解決の指摘 = レビュー本文・行コメント・通常コメントを一覧化して順に直す)。
   - `CLAUDE.md` の約束と既存のコード規約に従う。必要なテストも追加する。
   - 決めたことは `.claude/shared/decision-record.md` に従って記録する(実装と同じ commit に含める)。
   - 指摘が誤り・不適切と判断できる場合は、無視せず、対応しない理由を報告に書く。
   - **検証は段階的に行う。** 作業の途中と self-review の各反復では、触った言語・ディレクトリの lint・テストだけを実行する(`mise tasks` で個別タスクを確認する)。`mise run lint` と `mise run test`(web を変えたなら `cd apps/web && mise exec -- pnpm typecheck` も)の**全体実行は、push の直前に1回だけ**行う。
4. self-review(最大2回)。
   - 初回は `git diff origin/<デフォルトブランチ>...HEAD` 全体を、次の観点で読む: 要件充足 / 正確性 / 簡潔さ / テスト / 決定の記録(ADR を追加したなら一覧表も更新されているか、記録と設計書が食い違っていないか)。
   - 推測だけで指摘しない。コードで確認できた問題に絞り、見つけたら同じブランチ上で直す。
   - 2回目は、**直した差分だけ**を読む。指摘がなくなれば、そこで終える。残った指摘は報告に書く。
5. commit・push する。
   - 意味のある単位で commit する(日本語、既存の履歴の形式。例: `feat: ...` / `fix: ...`)。レビュー対応では、対応した指摘が分かるメッセージにする。
   - **通常モード**: `git push -u origin <ブランチ名>` のあと `gh pr create` する。
     - タイトルは commit と同じ形式。ベースはデフォルトブランチ。
     - 説明欄に `Closes #<番号>`、変更概要、self-review の結果、テスト結果、「決めたこと」(ADR へのリンク付き)を書く。
     - 作成したら、イシューの `status::in-progress` を外し、PR に `status::review-wait` を付ける。
   - **レビュー対応モード**: `git push` する。**確認なしで**レビュアー(指摘を投稿した人。自分自身と bot は除く)に `@<ログイン名>` で、`gh pr comment` により対応報告をする。内容は、対応内容(commit ハッシュ付き)、対応しなかった指摘と理由、再レビューのお願い。報告したら `status::fixing` を `status::review-wait` に付け替える。対応できず終えた場合も `status::fixing` は外す(`status::changes-requested` に戻す)。
6. 失敗して終える場合も、自分が付けた `status::in-progress` / `status::fixing` を必ず外すか元に戻す。

## 返す報告(短く)

PR の URL、実装の要約、記録した決定事項、self-review で直した点、未解決事項、起動した docker 等の一時リソース、worktree のパス
