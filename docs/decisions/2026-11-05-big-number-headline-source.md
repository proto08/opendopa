# 大きな数字・見出し・source.ref の決め方

- 日付: 2026-11-05
- Issue: #33
- 決定: 大きな数字の `value` は、`text` が数だけなら数(`countUp: true`)、そうでなければ `text` の最初の数、数がなければ `text`(`countUp: false`)。見出しは YAML の `headline`、なければ先頭の字幕の最初の文(40字を超えたら 39 字+「…」)。`source.ref` は行なら `行 #<row_id>`、group なら `列=値 / 列=値`(group_by の列)
