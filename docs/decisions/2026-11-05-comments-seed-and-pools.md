# コメントの種・件数・プールの決め方

- 日付: 2026-11-05
- Issue: #33
- 決定: コメントの種は `sha256("comments", videoId)`(`util.stable_int`)。件数は 6〜12、時刻は 0.5〜(長さ-0.5)秒を小数1桁で昇順。`calm` のプールからは「草」「ｗ」「w」「笑」を含む語を除く。`rule` に合う節がなければコメントなし。`rule` がなければ `light`(YAML が `pool_calm` だけを持つなら `calm`)。`calm` 以外のプールでは 15% が `yellow`
