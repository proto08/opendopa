# 小さな決定は1決定1ファイルにし、一覧は生成する

- 日付: 2026-11-05
- 決定: 小さな決定は `docs/decisions/YYYY-MM-DD-<slug>.md` に1決定1ファイルで書く。ADR と合わせた一覧は `mise run decisions-index`(`scripts/decisions_index.py`)が標準出力に出し、コミットしない。`docs/DECISIONS.md` は 2026-11-05 までの分としてそのまま残す。
- 理由: 全員が `docs/DECISIONS.md` の末尾に1行ずつ足すので、並行するPRが必ず衝突し、マージのたびに人が直していた。GitHub のサーバー側マージは `.gitattributes` の `merge=union` を使わないため、PR 画面の競合は設定では防げない。ファイルを分ければ構造的に衝突しない。
- 関連: ADR-0012 A11(使い分けは変えず、書き先だけ変える)
