# VOICEVOX の声は既定でずんだもん(ノーマル)・速度 1.0。クレジットは TTS_CREDIT で web に渡す

- 日付: 2026-11-06
- Issue: #60
- 決定: 声は `VOICEVOX_SPEAKER`(既定 3 = ずんだもん ノーマル)、速度は `VOICEVOX_SPEED`(既定 1.0)。フッターのクレジットは web が `TTS_PROVIDER=voicevox` のときだけ `TTS_CREDIT`(既定「VOICEVOX:ずんだもん」)を出す。声を変えたら `TTS_CREDIT` も合わせて変える
- 理由: スキーマにクレジットの欄がなく、声は pipeline の実行時の設定なので、環境変数を web と pipeline で揃えるのが最小。スタイルIDからキャラ名を引く表を持たない。実運用では利用規約の確認と、キャラ名の確認が必要
