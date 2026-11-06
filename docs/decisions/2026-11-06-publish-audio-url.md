# 音声の URL は MEDIA_BASE_URL を前に付けて作る

- 日付: 2026-11-06
- Issue: #38
- 決定: シーンの `lines[].audio.url` が相対(`<videoId>/<n>.mp3`)なら、publish が `MEDIA_BASE_URL` を前に付けて DB と Blob のシーンに書く。http(s) や `/` で始まるものはそのまま。音声ファイルは `out/<id>/media/<videoId>/<n>.mp3` から `media/` コンテナへ置く。
- 理由: 音声の生成(#60)はまだ無いが、イシューが MEDIA_BASE_URL を URL の基準と決めているため、受け取り側を先に決めた。#60 の出力先がこれと違えば合わせて直す。
