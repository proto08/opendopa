# 音声を入れたあとの長さは 15〜30 秒で再検査し、30 秒超は除外、15 秒未満は最後の行を延ばす

- 日付: 2026-11-06
- Issue: #60
- 決定: `tts` は、行の `durationSec` を音声の長さ + 0.3 秒(`LINE_PAD_SEC`。再生開始の遅れで末尾が切られないための余白)に置き換え、合計を動画の `durationSec` にして `gate.check_length` をやり直す。余白を足した合計で、30 秒を超えた動画は `scenes.jsonl` から外し、`videos.jsonl` を `excluded`(理由 `length`)にして `excluded.csv` に追記し、音声ファイルも消す。15 秒に満たないときは、最後の字幕の `durationSec` だけ延ばして 15 秒にする(`audio.durationSec` は音声の実際の長さのまま)。音声が短くなって動画の終わりより後ろになったコメントは落とす。`tts` は `scenes.jsonl` を上書きするので、やり直すときは先に `generate` を実行する
- 理由: `durationSec` は `lines` の合計という契約(2026-11-05 の字幕の秒数の決定)を保つため。短い音声を理由に除外すると、動画が大きく減る
- 関連: 2026-11-05-subtitle-seconds
