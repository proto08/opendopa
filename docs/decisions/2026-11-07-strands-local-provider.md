# 判断モデルは手元の PC で動かす(strands_local)。Azure への配備はデモの後

- 日付: 2026-11-07
- Issue: #165
- 決定: (1) モデル `StrandsAgents/strands-decider-2B-hobson-v19`(ベースは `Qwen/Qwen3.5-2B-Base` の LoRA。モデルもコードも Apache-2.0、ゲートなし)を、`strands_local` プロバイダーでプロセス内に読み込んで動かす(`strands_decider.infer.load_engine` → `SystemOneEngine.evaluate`。内部で `StrandsDeciderModel.load` を呼ぶ)。`strands-decider serve`(認証なし)は使わない。(2) 依存は pipeline の extra `decider`(`strands-decider>=0.3.0`)に分ける。(3) 選択・確信度は `strands_azure` とそろえる(choice は最大確率、noul は max(p, 1-p)、score はモデルの confidence)。choice の選択肢はモデルに日本語のラベルで見せ、答えを id に戻す(ラベルが重なるときだけ id)。(4) モデルは作る時点で1回だけ読む(エンジンの1問30秒の時間制限に入れないため)。読めなかったときは止めず、問いごとに失敗させて `rules` にフォールバックさせる。(5) デバイスは `STRANDS_LOCAL_DEVICE`、未指定なら cuda > mps > cpu。(6) `DECIDER_PROVIDER` の既定は `rules` のまま。Azure への配備(`strands_azure`)は、デモの後に回す。
- 確認できたこと: ダウンロードは、アダプタ約 67 MB と head・トークナイザ数十 MB に加え、ベース `Qwen/Qwen3.5-2B-Base` の safetensors 約 4.5 GB(Hub API で計測)で、合計約 4.6 GB。依存は PyTorch・transformers・peft・accelerate など(pipeline の `local` extra の `sentence-transformers` と PyTorch・transformers を共有する)で、`strands-decider` 自体は fastapi・uvicorn も引く。
- 未確認: 重みの実ダウンロード、実機での推論・速度(ブログの M3 約150 ms は未検証)、`decide --eval` での一致率。テストはモデルをモックしている。
- 理由: デモ前は pipeline をすべて手元で流す方針(2026-11-07-etl-job-and-video-refresh.md)で、Azure の配備(GPU/CPU の費用と準備)より早く試せる。評価用ラベルが未作成のため、合格するまで既定は `rules`。
- 関連: 2026-11-06-strands-azure-provider.md
