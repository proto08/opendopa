# csv_row と search_text の出し方

- 日付: 2026-11-05
- Issue: #33
- 決定: `csv_row` は、元の列(`derived` / `stats` 以外)を列の順に `[列名, 値]` で出し、欠損は `null`。個人に関わる列は YAML の `hide` で除く(既定は全部出す)。`search_text` は `embed_text` の空の穴を空にして詰めた文
