# GitHub の操作(REST)

Claude Code のクラウド環境では、`gh pr list` / `gh pr view` / `gh pr create` / `gh pr edit` / `gh pr comment` / `gh pr review` / `gh pr merge` / `gh issue ...` のように **GraphQL を使う `gh` のサブコマンドは 403 で失敗する**。最初から `gh api`(REST)を使う。失敗を確かめてから書き直さない。

`<R>` は `owner/repo`(`git remote get-url origin` の末尾2つ)。`<n>` は PR・イシューの番号。

| やること | コマンド |
| --- | --- |
| PR の情報 | `gh api repos/<R>/pulls/<n>` |
| PR の差分のファイル | `gh api repos/<R>/pulls/<n>/files --jq '.[].filename'` |
| PR の commit | `gh api repos/<R>/pulls/<n>/commits` |
| レビュー一覧 | `gh api repos/<R>/pulls/<n>/reviews` |
| 行コメント | `gh api repos/<R>/pulls/<n>/comments` |
| 通常コメント | `gh api repos/<R>/issues/<n>/comments` |
| CI の結果 | `gh api repos/<R>/commits/<head sha>/check-runs --jq '.check_runs[]\|[.name,.status,.conclusion]\|@tsv'` |
| レビューを投稿(COMMENT) | `gh api repos/<R>/pulls/<n>/reviews -f event=COMMENT -f body="$(cat 本文.md)"` |
| コメントを投稿 | `gh api repos/<R>/issues/<n>/comments -f body="$(cat 本文.md)"` |
| ラベルを付ける | `gh api -X POST repos/<R>/issues/<n>/labels -f 'labels[]=status::review-wait'` |
| ラベルを外す | `gh api -X DELETE repos/<R>/issues/<n>/labels/status::review-wait` |
| PR を作る | `gh api repos/<R>/pulls -f title=... -f head=<branch> -f base=main -f body="$(cat 本文.md)"` |
| マージ | `gh api -X PUT repos/<R>/pulls/<n>/merge -f merge_method=merge -f sha=<head sha>` |

- 本文は、一度ファイルに書いてから `$(cat ...)` で渡す(引用符や改行の事故を避ける)。
- マージは必ず `sha` を付ける(確認した head と違う commit をマージしないため)。405 は、main が進んだなどで一時的にマージできない印。`mergeable_state` を取り直して、`clean` なら1回だけ再試行する。
- ラベルの付け替えは、付ける → 外す の順に2回呼ぶ(`status::*` は排他。`docs/kanban.md`)。
- 一覧が100件を超えるときは `--paginate` を付ける。
