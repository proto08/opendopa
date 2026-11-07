# Terraform の openai・storage・cdn を enable_* で任意にして、最小構成から始められるようにする

- 日付: 2026-11-07
- Issue: #131
- 決定: `openai`・`storage`・`cdn` の各モジュールに `count` を付け、変数 `enable_openai` / `enable_storage` / `enable_cdn`(既定はすべて `true`)で作らない選択ができる。`infra/modules/openai`、`infra/main.parameters.json`、`outputs.tf` の `azure_openai_*` は残す(無効のときの出力は `null`)。`enable_cdn = true` には `enable_storage = true` が必要(validation)。`enable_openai = false` のとき、web・recsys に渡す `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_EMBED_DEPLOYMENT` は空文字になり、`AZURE_OPENAI_API_KEY` のシークレットは作らない(参照は `module.openai[0]` で、条件付き)。`MEDIA_BASE_URL` は、cdn があれば Front Door、なければ Blob の URL、storage もなければ空。`.env.example` に `TF_VAR_postgres_admin_password` / `TF_VAR_internal_token` を足した
- 理由: Azure の 30 日無料試用で、クォータの制約や失敗の切り分けを避け、最小構成(RG、ACR、Log Analytics、Postgres、Container Apps)から始められるようにするため。`enable_openai = false`・`enable_cdn = false`・`enable_storage = false` で成り立つ。既定値は現在の構成を変えない
- 注意: `2026-11-07-embed-azure-openai-again.md`(埋め込みは Azure OpenAI、`infra/modules/openai` は削除せず使う)と矛盾しない。モジュールは残し、既定で作る。最小構成のときだけ `enable_openai = false` にして、埋め込みは別の手段(`EMBED_PROVIDER=local` など)にする。`terraform plan` / `apply` は実行していない(`validate` のみ)
- 関連: ADR-0017 A4
