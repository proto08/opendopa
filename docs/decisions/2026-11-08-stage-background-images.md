# 動画の背景に、データセットごとの画像を敷く(web 側の対応表)

- 日付: 2026-11-08
- Issue: #179(子 #180〜#183)
- 決定:
  - 背景画像 5 枚(drone / home / car / ship / train)を `apps/web/public/bg/` に置いて git 管理する。
  - データセット → 画像の対応表は `apps/web/lib/background.ts` に 1 か所だけ持つ。シーンJSON・DB・pipeline は変えない。
    - drone: accident, flightplan / home: akiya_reg, akiya_sold / car: rental_result, rental_fleet / ship: naiko_route, naiko_ship / train: rail_* の 6 つ
  - 描画は web の `Stage`(ブラウザ描画)。Remotion は使わない(設計書 §1.2 の非ゴールのまま)。
  - 重ね順は、紺のグラデーション → 背景画像 → 暗くするレイヤー(上下を濃く)→ 透かし 1 文字(画像があるときは薄く)→ 既存の UI。
  - 本番へは、`apps/web/Dockerfile` が `public/` をイメージに含めるので、`mise run deploy` でそのまま反映する。
- 理由:
  - スキーマ変更、`gen-types`、約 2,100 本の再公開が要らず、ハッカソン最終日に変更を小さくできる。
  - 画像の出どころは Gemini の生成(半写実のイラスト)。設計書 §1.2 の「生成AIによる写実的な映像」は非ゴールのままで、写実ではないイラストとして使う。「AI生成」ラベルは常に表示される。
  - 行ごとに画像を変えたくなったら、そのとき `scene.schema.json` に `background` を足す。
- 関連: 画像は 360×640 で、大きなステージでは柔らかく見える。高解像度への差し替えは #183。
