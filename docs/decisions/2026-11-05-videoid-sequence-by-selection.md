# videoId の連番は選定の順にする

- 日付: 2026-11-05
- Issue: #33
- 決定: `videoId` の連番は選定の順(除外した行も数える)。
- 理由: 除外の条件を変えても、残る動画の ID が変わらないため。除外された行も `videos.jsonl` に `status: excluded`、`excluded_why` つきで出す(`scenes.jsonl` には出さない)。
