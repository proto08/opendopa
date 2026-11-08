# デモ用の字幕は `strands_local` で作り、確信度の閾値 0.55 はそのままにする

- 日付: 2026-11-08
- Issue: #175
- 決定: デモ用の全 14 データセット(動画 1,815 本)の字幕は、`DECIDER_PROVIDER=strands_local` で作る。`min_confidence: 0.55` は変えない。確信度が届かない判断は `rules` に戻る(設計書 §8.3a)。`DECIDER_PROVIDER` の既定は `rules` のまま(評価ラベルがなく、一致率 80% 以上・フォールバック 30% 以下を確かめられていないため)。
- 理由: フォールバックが 30% を超えるのは 6 データセット(rail_pl 41%、rail_traffic2 55%、naiko_ship 66%、naiko_route 69%、rental_fleet 71%、rail_km 75%)。原因は推論の失敗(確信度 0)ではなく、選択肢が 3〜4 個で確率がほぼ均等になり、最大の確率が 0.55 に届かないこと。閾値を下げるとモデルの判断が増えるが、当てずっぽうの選択も混ざる。評価ラベルがないので、下げてよいかを判断する根拠がない。デモ前日だったので、安全弁の 0.55 を残した。accident・rail_traffic1・rail_bs などは、モデルの判断が主になる。
- 関連: `docs/decisions/2026-11-07-strands-local-provider.md`
