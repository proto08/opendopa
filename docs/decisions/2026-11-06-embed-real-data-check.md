# 実データで embed を確認し、同名のクラスタ名を避ける

- 日付: 2026-11-06
- Issue: #37
- 決定: accident(02_jikojyouhou.csv)を `generate --provider rules` で動画化し、`embed --provider local` を実行して確認した。結果は下記。確認で見つかった「同名のクラスタが複数できる」不具合を直し、機械的なクラスタ名は他のクラスタと重なるとき、次に多い地域・種別を「・」でつなぐ(それでも重なれば「(2)」)ようにした。
- 理由: accident だけだと 12 クラスタ中 6 つが「事故等報告の事故」になり、見分けがつかなかった。
- 結果(local = intfloat/multilingual-e5-large、CPU、sentence-transformers 導入済みの環境):
  - generate: 189 本(除外 5 行)、約 1 秒
  - embed: 189 本・12 クラスタ、約 34 秒(モデルは取得済み。他データセットも混ぜた 780 本・12 クラスタでは約 2 分 24 秒)
  - 出力: `embeddings.npz`(video_id[189] / embedding[189,1024] float32 / x / y / cluster_id[189] int32 / model)、`clusters.json`(id・name・color・centroid[1024]・cx・cy の配列)、`centroid.json`(model と全体の centroid[1024])
  - 未確認: Azure(資格情報がないため使っていない)、`--llm` によるクラスタ名、publish への取り込み
  - 副産物: data/raw があると走る `test_generate_accident_real` は、推定秒数の最小を 19〜20 としていたが、実データでは 18.31 だった(#37 以前から。CI は data/raw がなく skip)。下限を 18 に直した。
