# sleep: コンフリクト解消担当(自分のPRごと)

`CONFLICTING` になっている**自分の**PRのコンフリクトを解消し、条件を満たせばマージする。他の人のPRには使わない(他人のブランチは書き換えない)。

入力: PR番号。原則は呼び出し元のプロンプトで渡される。

## 手順

1. PR のラベルを `status::conflict` にする。元のラベル(`status::review-wait` など)は覚えておく。
2. worktree を `../opendopa-<イシュー番号 or PR番号>` に用意する(既存があり未pushの変更がなければ再利用、あれば別名)。PRの head ブランチをチェックアウトする。
3. `git fetch origin` のあと、`git merge origin/<デフォルトブランチ>` で取り込む。**rebase と force push はしない**(履歴を書き換えない)。
4. コンフリクトを解消する。
   - `docs/DECISIONS.md` などの追記系は、両方の行を残す。
   - コード・スキーマは、双方の意図(PRの説明欄・イシュー・main 側の該当 commit)を読んで統合する。生成物(`packages/shared/src/generated/` など)は手で直さず、元(JSON Schema)を統合して `mise run gen-types` で再生成する。
5. 検証する。`mise run lint` と `mise run test`(web を変えたなら `cd apps/web && mise exec -- pnpm typecheck` も)。
6. 通ったら merge commit を `git push origin <ブランチ名>` で push する。コミットメッセージは日本語(例: `merge: main を取り込みコンフリクトを解消`)。PRに、解消した内容を2〜3行で `gh pr comment` する。
7. **次をすべて満たすとき、確認なしで自分のPRをマージする。**
   - 解消のためのマージで、コンフリクトの解消以外のコード変更を加えていない(指摘対応などの別の変更が混ざっていない)。
   - 未対応のレビュー指摘が残っていない(`gh pr view <番号> --json reviews,comments` で確認)。
   - ローカルの lint・test が通っている。
   - `.claude/shared/merge-rules.md` の確認を満たす(解消後に再びコンフリクトしていない、変更要求が残っていない、CI に失敗がない)。
   - 満たさない、または判断に迷う場合はマージしない。理由を報告に書く(レビュアーがいるときは、再レビューが必要かを一言添えてコメントする)。
8. **解消できない・判断に迷う場合は push しない。** `git merge --abort` で元に戻し、コンフリクトしたファイルと理由(双方の意図が両立しない、など)を報告する。PRには事実だけを短くコメントしてよい。
9. 終わったら `status::conflict` を、覚えておいた元のラベルに付け替える(元がなければ外す)。解消できなかった場合も同じ。マージしたときはワークフローが外すので何もしない。
10. 後片付け: `git status --porcelain` が空で `git log origin/<ブランチ名>..HEAD` も空なら、worktree を `git worktree remove` で削除する。ブランチは削除しない。

## 返す報告(短く)

PR番号、コンフリクトしたファイルと解消方針、push した commit、テスト結果、マージしたか(しなかった理由)、クローズされたイシュー、解消できなかった場合の理由
