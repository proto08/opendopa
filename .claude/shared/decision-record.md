# 決定事項の記録(ADR / docs/decisions/)

実装・レビュー対応の中で決めたことは、規模に応じて次の2か所に残す。記録は実装と同じcommit(または同じPR)に含める。

| 種類 | 書き先 | 目安 |
| --- | --- | --- |
| イシュー単位の大きな決定 | `docs/adr/NNNN-<description>.md`(NNNN はイシュー番号を4桁ゼロ埋め) | ツール・構成・境界など、後から覆すと影響が大きく、理由まで残したいもの |
| 実装中に決めた小さな決定 | `docs/decisions/YYYY-MM-DD-<slug>.md`(1決定1ファイル) | ライブラリの選択、命名、挙動の細かい判断など |

- **小さな決定**: `docs/decisions/YYYY-MM-DD-<slug>.md` を1決定につき1ファイル作る。形式は `docs/decisions/README.md` のとおり。日付は `date +%F` で取得する。`docs/DECISIONS.md` には足さない(複数のPRが同じ場所に追記して衝突するため。2026-11-05 より前の分だけがそこにある)。
- **ADR**: `docs/adr/NNNN-<description>.md` を作成する(既存ファイルがあれば追記・更新する)。形式は次のとおり。決定ごとに `A1`, `A2`, ... と連番を振る。
  ```markdown
  # ADR-NNNN <題>

  - Issue: #<番号>
  - 日付: YYYY-MM-DD
  - 状態: 決定

  ## A1 <決定の題>

  - 決定: ...
  - 理由: ...
  ```
  - 一覧表への追記は不要。ADR と小さな決定の一覧は `mise run decisions-index` が `docs/adr/` と `docs/decisions/` から生成する(索引はコミットしない)。
- 設計書(`docs/design_doc.md` など)の内容と食い違う決定をした場合は、設計書も合わせて更新する。イシュー本文は更新せず、読み替えが必要なら PR 説明欄に書く。
- 決定がなければ、何も作らない(空のADRや「なし」の記録は不要)。
- 他の決定と矛盾しないよう、書く前に既存の `docs/adr/`、`docs/decisions/`、`docs/DECISIONS.md` を読む(`mise run decisions-index` で一覧が見られる)。
