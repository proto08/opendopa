# 埋め込みは Azure OpenAI(`text-embedding-3-small`)を使う(2026-11-07-no-azure-openai-local-models.md の埋め込みの部分を取り消す)

- 日付: 2026-11-07
- 決定: 埋め込みの既定を `EMBED_PROVIDER=azure`(Azure OpenAI `text-embedding-3-small`、`dimensions=1024`)にする。`local`(`multilingual-e5-large`)は代わりの実装として残す。チャットモデルは使わず `LLM_PROVIDER=none` のまま。`infra/modules/openai` は削除せず使う(チャットのデプロイは不要)
- 理由: ユーザー(proto08)の判断。判断モデルを Azure に置く方針(`2026-11-07-decider-on-azure-again.md`)に合わせ、本番側にモデルを置く方針に戻す
- 注意: `azure` と `local` は次元(1024)が同じでもモデルが違うので、ベクトルを混ぜない。切り替えたら全動画を埋め込み直す。コードの `provider_name_from_env()` の既定値は `local` のままなので、`.env.local` で `EMBED_PROVIDER=azure` を指定する。Azure のサブスクリプションが書き込み禁止のため、デプロイと実接続は未確認
