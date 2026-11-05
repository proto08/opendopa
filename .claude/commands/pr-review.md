---
description: PRをイシューと照らしてレビューし、許可を得てレビューコメントを投稿する(指摘がなければマージする)
argument-hint: "[PR番号]"
---

# PR レビュー

引数: `$ARGUMENTS`(PR番号。省略可)

以下の手順を順に実行する。

## 0. main の最新化(最初に必ず実行)

他の手順より前に、メインの作業ディレクトリで main を最新にする。コマンド定義(`.claude/commands/`)も main に含まれるため、これで常に最新の手順で動く。

- `git status --porcelain` と `git branch --show-current` を確認する。
- 現在のブランチが main で、未コミットの変更がなければ `git pull --ff-only origin main` を実行する。
- 現在のブランチが main 以外、または未コミットの変更がある場合は、`git checkout` / `git switch` をせず、`git fetch origin` だけを行い、main を更新できなかった旨を伝える。
- `--ff-only` で失敗した場合は、無理に merge / reset せず、その旨を伝える。
- pull で `.claude/commands/` の内容が変わった場合は、このコマンドの定義を読み直し、最新の内容に従って以降を実行する。

## 1. 対象PRの特定

- `gh pr list --state open --limit 1000 --json number,title,author,headRefName,updatedAt` でオープンなPRを取得する。
- 引数が空、または指定番号のPRが存在しない(オープンでない場合を含む)場合:
  - オープンなPRが1件のみ → それを自動で選択する。
  - 2件以上 → 番号・タイトル・作成者・ブランチ・更新日時をMarkdownテーブルで表示し、ユーザーに番号を尋ねて待機する(存在しない番号を指定された場合はその旨も伝える)。
  - 0件 → その旨を伝えて終了する。
- 引数が存在するPR番号なら、それを対象とする。

## 2. worktree へのチェックアウト

差分が文書だけ、または CI が成功済みでコードを実行する必要がない場合は、worktree を作らず `gh pr diff` だけでレビューしてよい(`.claude/shared/review-criteria.md`)。以下は worktree を作る場合。

進行中の他作業を壊さないため、現在の作業ディレクトリでは `git checkout` / `git switch` を行わない。

- `gh pr view <番号> --json headRefName,headRepositoryOwner,isCrossRepository` でソースブランチを確認する。
- `git fetch origin pull/<番号>/head:pr-<番号>-review` などでブランチを取得し(フォークPRも対応可能)、
  `git worktree add ../opendopa-pr-<番号> pr-<番号>-review` で独立した作業ディレクトリを作る。
- 既に同名のworktreeがある場合は、内容を確認してから再利用するかユーザーに尋ねる。
- 以降のファイル参照・テスト実行などはこのworktree内で行う。
- 状態ラベル(`docs/kanban.md`)を `status::pr-review` にする(既存の `status::*` は同じコマンドで外す)。ラベルの付け替えは、コメントの投稿ではないので許可は要らない。

## 3. イシューの特定とレビュー

- `gh pr view <番号>` でPR説明欄を読み、関連イシュー(`Closes #N` / `Fixes #N` / `#N` / URL 等)を特定する。`gh issue view <N>` で要求事項・タスクを把握する。特定できなければユーザーに尋ねる。
- `.claude/shared/review-criteria.md` を読み、その観点(要件 / 正確性 / 簡潔さ / テスト / 決定の記録)で、`gh pr diff <番号>` と worktree 上のコードをレビューする。
- 記録が妥当かどうかの判断自体に迷う場合は、断定せずユーザーに確認する。
- テスト・lint は、review-criteria.md の「実行するかの判断」に従い、必要な範囲だけ実行する。後片付けが必要になるもの(捨てdockerコンテナ等)を起動した場合は、何を起動したか記録しておく。

## 4. レビュー結果の提案(投稿はまだしない)

各指摘を以下の形式でユーザーに提示する。

- **ファイルパス:行番号**
- **観点**(要件 / 正確性 / 簡潔さ / テスト / 決定の記録)
- **問題**: 何が問題か
- **修正案**: 具体的な修正内容(必要ならコード例)

指摘がない観点もその旨を一言添える。最後に総評(approve / request changes / comment のどれが妥当か)を示す。

## 5. コメント投稿(必ずユーザーの許可を得る)

- **ユーザーの明示的な許可なしにPRへコメント・レビューを投稿してはならない。**
- 投稿する指摘の取捨選択・文面修正をユーザーに確認し、許可後に `gh pr review` または `gh api`(行コメント)で投稿する。
- 投稿種別(approve / request changes / comment)もユーザーに確認する。
- 投稿後(投稿せず終える場合も)、`status::pr-review` を付け替える。指摘を投稿したら `status::changes-requested`、指摘なしなら `status::ready-to-merge`、投稿しないなら外す。

## 5a. 指摘がなければマージする

手順 4 の結果が**指摘なし**(ユーザーに確認したい点も含め、1件も残っていない)なら、このコマンドの定義がマージの許可になるので、追加の確認なしでマージする。指摘が1件でもある場合・判断に迷う場合は**マージしない**。

`.claude/shared/merge-rules.md` に従って確認し、マージする(確認項目、CI の待ち方、権限拒否時の再試行、ラベルの扱いもそこにある)。レビュー中に実行したテスト・lint が通っていることも条件に含める。マージしなかったときは、理由を伝え、ラベルは `status::ready-to-merge` のままにする。

## 6. 後片付け

コメント投稿後(または投稿せず終了する場合も)、以下の後片付けを提案する。

- 作成した worktree(`git worktree remove ../opendopa-pr-<番号>`)とローカルブランチ(`pr-<番号>-review`)
- レビュー中に起動した捨てdockerコンテナ・ボリューム・ネットワーク等
- その他の一時ファイル

削除対象の一覧を示し、**ユーザーの許可を得てから**削除する。未コミットの変更がある場合は、削除前に警告する。
