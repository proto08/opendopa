# strands_azure はAPI(POST /v1/decide)を呼ぶ。既定は rules のまま、配備と評価は人が行う

- 日付: 2026-11-06
- Issue: #58
- 決定: (1) `strands_azure` プロバイダーは `STRANDS_DECIDER_URL` の `POST /v1/decide` に問いの配列を送り、選択肢ごとの確率(choice)・はいの確率(noul)・期待値(score)を受け取る。選択と確信度(最大確率。noul は max(p, 1-p))はプロバイダーが作る。`Authorization: Bearer $STRANDS_DECIDER_TOKEN` を付ける。HTTP は標準ライブラリ(urllib)で呼び、依存を増やさない。(2) 失敗(5xx・接続・タイムアウト)は例外で返してエンジンの `rules` フォールバックに任せる。1件だけ形が壊れた結果は確信度0にして、同じくフォールバックさせる。(3) 配備先は `infra/modules/decider`(構成は 2026-11-06-decider-cpu-external.md で CPU・外部 ingress に変更した)。`decider_enabled = false` が既定で、`terraform apply` しても GPU は作られない。(4) `DECIDER_PROVIDER` の既定は `rules` のまま。(5) `decider_enabled = true` で `decider_token` が空・16文字未満なら、モジュールの `token` のバリデーションで plan が失敗する(空のシークレットで配備しない)。(6) 外部 ingress にしたので、パイプラインは手元 PC・CI からも届く(VNet・private DNS は不要)。(7) モデルの入手元・ライセンス、費用、事故50行の評価(§14.2b)は未実施。
- 理由: 配備(GPU の費用)と実接続は人の確認が要り、評価用ラベル(`datasets/accident.labels.csv`)も未作成のため、合格判定ができない。設計書どおり、評価を通すまでは `rules` を既定にする。API の形は実モデルのサーバーを作るときの契約になる(変えるときはこの決定と `strands_azure.py` の docstring を直す)。
