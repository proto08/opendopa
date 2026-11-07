# 判断モデルは Azure 上の自前モデル(`strands_azure`)で動かす(2026-11-07-no-azure-openai-local-models.md の判断モデルの部分を取り消す)

- 日付: 2026-11-07
- Issue: #58
- 決定: 判断モデルは、Azure 上の Container App(本体と同じ Container Apps Environment、CPU、外部 ingress + Bearer トークン)で動かす自前モデルを使う(`DECIDER_PROVIDER=strands_azure`)。評価(§14.2b)に合格するまでは `rules` が既定。`jev_local` は残すが、既定の候補ではない。埋め込みは Azure OpenAI(`EMBED_PROVIDER=azure`)に戻す(`2026-11-07-embed-azure-openai-again.md`)。チャットモデルは使わない(`LLM_PROVIDER=none`)
- 理由: ユーザー(proto08)の判断。本番の側にモデルを置く方針に戻す
- 注意: Azure のサブスクリプションが書き込み禁止(`ReadOnlyDisabledSubscription`)のため、配備と実接続は未確認。モデルの入手元・ライセンス・費用も未確認
