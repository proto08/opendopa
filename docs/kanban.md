# 看板(状態ラベルと GitHub Projects)

`/sleep`・`/start-task`・`/pr-review` が、いま何をしているかを GitHub に出すための取り決め。エンジニア複数人の AI が同時に動いても、GitHub Projects の Board で全体を見られる。

- 正は **ラベル `status::*`**。エージェントはラベルだけを書く(`gh issue edit` / `gh pr edit`)
- `.github/workflows/project-status.yml` が、ラベルの変化を Projects の **Status** 項目に同期する(列になる)
- 担当者は assignee(イシュー)と作成者(PR)で分かる。Board を assignee でグループ化すると、人ごとの行になる

## 状態ラベル

状態は排他。1つのイシュー/PRに付く `status::*` は常に1つ以下にする。付け替えは **1回のコマンドで** `--add-label 新 --remove-label 旧` と書く(GitHub は排他を保証しない)。

| ラベル | Project の Status | 対象 | 意味 |
| --- | --- | --- | --- |
| `status::in-progress` | In Progress | イシュー | 実装中(worktree を作ってから、PR を作るまで) |
| `status::review-wait` | Review wait | PR | レビュー待ち(PR 作成直後、修正の push 後) |
| `status::pr-review` | PR review | PR | AI がレビュー中 |
| `status::changes-requested` | Changes requested | PR | 指摘を投稿済み。作成者の対応待ち |
| `status::fixing` | Fixing | PR | 作成者側の AI が指摘対応中 |
| `status::merge-check` | Merge check | PR | レビューした側の AI が、指摘の対応を確認中 |
| `status::conflict` | Conflict | PR | AI がコンフリクトを解消中 |
| `status::ready-to-merge` | Ready to merge | PR | 指摘なし。人のマージ待ち |
| (ラベルなし/クローズ) | Todo / Done | 両方 | ラベルが全部外れたら Todo。クローズ・マージで Done |

## 遷移

```
イシュー: (Todo) → in-progress → [PR を作ったら外す] → (クローズで Done)
PR:       review-wait → pr-review → changes-requested → fixing → review-wait → …
                              └→ ready-to-merge        merge-check → (マージで Done)
          conflict(解消中だけ。終わったら直前の状態に戻す)
```

- PR を作ったら、イシューの `in-progress` を外し、PR に `review-wait` を付ける(カードが二重に動かないよう、以降は PR の状態だけを動かす)
- 作業を終えるとき(成功・失敗・中断のどれでも)、自分が付けた作業中の状態(`in-progress` / `pr-review` / `fixing` / `merge-check` / `conflict`)は必ず外すか、次の状態に付け替える
- ラベルの付け替えは、他人のPRにも行ってよい(投稿ではない)。ただし、付けてよいのはこの表の状態だけ

## 他の人の作業中を避ける

他の人の AI が `pr-review` / `merge-check` を付けて作業中のPRに、重ねて着手しない。

- 判定: `gh api repos/{owner}/{repo}/issues/<番号>/events` で、そのラベルの最後の `labeled` イベントを探し、`actor.login` が自分でなく、`created_at` が **3時間以内**なら「他の人が作業中」とみなして飛ばす
- 3時間を超えていれば、残骸とみなして無視してよい(外さない。他人のラベルは触らない)

## 残骸の掃除

AI が落ちると、作業中のラベルが残る。`/sleep` は最初のラウンドの開始時に、**自分が付けたもの**だけを外す。

- 自分が担当のイシューの `status::in-progress`
- 自分が作成者のPRの `status::fixing` / `status::conflict`
- 他の人のPRの `status::pr-review` / `status::merge-check` のうち、最後の `labeled` イベントの `actor` が自分のもの

外したあとにサブエージェントを起動する前の状態に戻すことはしない(ラベルなし = Todo。状態が分からないことを示す)。

## 限界

- 粒度は「どの段階か」まで。「self-review の何周目」「テスト実行中」までは出ない
- 落ちた AI の残骸は、上の掃除が動くまで残る(他人の分は 3 時間で無視される)

## セットアップ(1回だけ)

1. GitHub Projects(v2)を作り、Board ビューを追加する。Status 項目の選択肢を、上の表の **Project の Status** 列の名前どおりに用意する(`Todo` と `Done` を含む。名前が違うと同期が失敗する)
2. Project の組み込みワークフロー「Auto-add to project」で、このリポジトリのイシューとPRを自動追加する
3. Board を assignee でグループ化する(人ごとの行)
4. リポジトリ変数 `PROJECT_NUMBER` に、Project の番号を入れる。`Settings → Secrets and variables → Actions → Variables`
5. リポジトリ Secret `PROJECT_TOKEN` に、Project を更新できるトークンを入れる(`project` 権限を持つ PAT、または GitHub App のトークン)。既定の `GITHUB_TOKEN` では、ユーザー/Organization 所有の Project は更新できない
6. ラベルを作る(`gh label create "status::in-progress" --color ...` を各ラベルに)

`PROJECT_NUMBER` と `PROJECT_TOKEN` が未設定の間、ワークフローは何もせず成功で終わる。
