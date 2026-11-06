# accident の評価用ラベルは未作成のまま。rules の下書きでの一致率は評価に使わない

- 日付: 2026-11-06
- Issue: #35
- 決定: `datasets/accident.labels.csv` はコミットしない。実データ(`data/raw/accident/02_jikojyouou.csv`)で `decide --draft` を実行して50行の下書きは作れた(型の内訳: 負傷14・制御不能13・物件13・その他10)。ただし下書きは `rules` 自身の判断なので、これに対する `rules` の一致率100%(50/50)は自己一致であり、精度の根拠にしない。測れた値は次の2つだけ。フォールバック0%(0/50)、1問あたりの時間 0.000秒(`rules` は規則の評価だけで実質0)。
- 理由: 正解は人が事故等の記述を読んで付けるもので、自動では正しく付けられない。下書きをそのまま正解として置くと、一致率が実力と無関係に100%になる。残りの作業: 人が下書きの `template` を50行ぶん直して `datasets/accident.labels.csv` を置き、`mise exec -- uv run opendopa decide --dataset accident --eval datasets/accident.labels.csv --provider rules`(LLM は `--provider` に追加)で再計測する。手順: `cd pipeline && mise exec -- uv run opendopa decide --dataset accident --draft`(`data/raw` に実データが必要)。
