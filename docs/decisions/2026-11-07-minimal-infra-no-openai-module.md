# Terraform から openai モジュールを外し、storage と cdn を任意にする

- 日付: 2026-11-07
- Issue: #131
- 決定: `infra/modules/openai` と `infra/main.parameters.json`、`outputs.tf` の `azure_openai_*` を削除した。Azure OpenAI は Terraform では作らず、使うときは Azure で手動で作って `AZURE_OPENAI_*` を渡す(`.env.example` の `AZURE_OPENAI_*` はコードが読むので残し、見出しに「Terraform では作らない」と書いた)。`storage` と `cdn` は `enable_storage` / `enable_cdn`(既定 `true`)で作らない選択ができる。`enable_cdn = true` には `enable_storage = true` が必要(validation)。`MEDIA_BASE_URL` は、cdn があれば Front Door、なければ Blob の URL、storage もなければ空。`.env.example` に `TF_VAR_postgres_admin_password` / `TF_VAR_internal_token` を足した
- 理由: Azure の 30 日無料試用で、失敗の切り分けとクォータの制約を避け、最小構成(RG、ACR、Log Analytics、Postgres、Container Apps)から始められるようにするため。既定値は現在の構成を変えない
- 注意: `2026-11-07-embed-azure-openai-again.md` の「`infra/modules/openai` は削除せず使う」の部分と食い違う。イシュー #131(その後に作成)の指示に従った。埋め込みを Azure OpenAI にする場合は、リソースを手動で作るか、モジュールを戻す。`terraform plan` / `apply` は実行していない
- 関連: ADR-0017 A4(取り消し)
