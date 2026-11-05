# マージの共通規則

`/pr-review` と `/sleep` の各役割が、マージの直前に共通で使う。マージしてよいかどうかの**許可そのもの**は、呼び出し元のコマンド定義が与える。この文書は「どう確認し、どう実行するか」だけを定める。

## マージ前の確認

次のコマンド1回で必要な値を取る(必要な項目だけ)。

```bash
gh pr view <番号> --json isDraft,mergeable,reviewDecision,statusCheckRollup
```

すべて満たすときだけマージする。1つでも欠ける、または判断に迷う場合はマージしない。

- ドラフトではない。
- `mergeable` が `MERGEABLE`。`UNKNOWN` は GitHub が計算中なので、少し間隔をあけて**1回だけ**取り直す。それでも `UNKNOWN` ならマージしない。
- `reviewDecision` が `CHANGES_REQUESTED` ではない。
- CI の確認(下記)で失敗がない。CI がなければ問わない。
- 呼び出し元が求めるテスト・lint が通っている。

## CI の待ち方(無制限に待たない)

- `statusCheckRollup` がすべて成功 → 次へ。
- 失敗がある → マージしない。事実(どのチェックが失敗したか)だけを伝える。
- 実行中がある → `timeout 600 gh pr checks <番号> --watch` で最大10分だけ待つ。タイムアウトしたら、マージせず「CI待ちで見送り」と報告して次へ進む(ループ全体を止めない)。

## マージの実行

- `gh pr merge <番号> --merge`(履歴が `Merge pull request #N` の形式のため)。**ブランチは削除しない**。
- マージ後、`gh pr view <番号> --json state,closingIssuesReferences` で、`Closes #N` のイシューがクローズされたことを確認する。
- 権限判定(Claude Code の許可)で拒否された場合は、一時的な誤判定の可能性があるので、同じコマンドをそのまま再試行する(間隔をあけて最大3回)。それでも拒否されたら、別のコマンド・API・設定ファイルの書き換えなどで回避せず、「マージ可能と判断したが権限で拒否された」と報告して次へ進む。

## ラベル

- マージしたとき: ワークフローが `status::*` を外すので、何もしない。
- マージしなかったとき: 呼び出し元の指定に従う(`status::ready-to-merge` のまま、または `status::changes-requested` へ)。
