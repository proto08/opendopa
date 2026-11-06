# 音声は mp3 で持ち、長さは mutagen で測る(VOICEVOX の wav は lameenc で変換)

- 日付: 2026-11-06
- Issue: #60
- 決定: 音声は `out/<id>/media/<videoId>/<n>.mp3` に置き、`lines[i].audio.url` は `<videoId>/<n>.mp3` の相対パスにする(`publish` が MEDIA_BASE_URL を前に付け、Blob の `media` に `<videoId>/<n>.mp3` で上げる)。長さは `mutagen` で測る。VOICEVOX は wav を返すので `lameenc`(純粋な mp3 エンコーダ。ffmpeg 不要)で mp3 にする。Azure は mp3 形式を指定して受け取る。HTTP は標準ライブラリで呼ぶ(SDK は入れない)
- 理由: Blob の配信と `publish`(#114)が mp3 前提。ffmpeg を必須にするとセットアップが増えるため
