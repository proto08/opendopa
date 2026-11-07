output "resource_group_name" {
  description = "リソースグループ名"
  value       = azurerm_resource_group.main.name
}

output "location" {
  description = "リージョン"
  value       = azurerm_resource_group.main.location
}

output "log_analytics_workspace_id" {
  description = "Log Analytics ワークスペースのリソース ID"
  value       = module.monitoring.log_analytics_workspace_id
}

output "application_insights_connection_string" {
  description = "APPLICATIONINSIGHTS_CONNECTION_STRING に設定する値"
  value       = module.monitoring.application_insights_connection_string
  sensitive   = true
}

output "registry_name" {
  description = "Container Registry の名前"
  value       = module.registry.name
}

output "registry_login_server" {
  description = "Container Registry のログインサーバー(docker push の宛先)"
  value       = module.registry.login_server
}

output "postgres_fqdn" {
  description = "PostgreSQL のホスト名"
  value       = module.postgres.fqdn
}

output "postgres_database_name" {
  description = "DB 名"
  value       = module.postgres.database_name
}

output "database_url" {
  description = "DATABASE_URL に設定する値(管理者ロール。recsys 用の読み取り専用ロールはマイグレーションで作る)"
  value = format(
    "postgres://%s:%s@%s:5432/%s?sslmode=require",
    module.postgres.administrator_login,
    urlencode(var.postgres_admin_password),
    module.postgres.fqdn,
    module.postgres.database_name,
  )
  sensitive = true
}

output "storage_account_name" {
  description = "Blob の Storage Account 名"
  value       = var.enable_storage ? module.storage[0].name : null
}

output "storage_connection_string" {
  description = "STORAGE_CONNECTION_STRING に設定する値(パイプラインの publish 用)"
  value       = var.enable_storage ? module.storage[0].primary_connection_string : null
  sensitive   = true
}

output "media_base_url" {
  description = "MEDIA_BASE_URL に設定する値(Front Door。enable_cdn = false なら Blob の URL、enable_storage = false なら空)。音声は /media/、シーンJSONは /scenes/"
  value       = local.media_base_url
}

output "azure_openai_endpoint" {
  description = "AZURE_OPENAI_ENDPOINT に設定する値(enable_openai = false なら null)"
  value       = var.enable_openai ? module.openai[0].endpoint : null
}

output "azure_openai_api_key" {
  description = "AZURE_OPENAI_API_KEY に設定する値(enable_openai = false なら null)"
  value       = var.enable_openai ? module.openai[0].primary_access_key : null
  sensitive   = true
}

output "azure_openai_embed_deployment" {
  description = "AZURE_OPENAI_EMBED_DEPLOYMENT に設定する値(enable_openai = false なら null)"
  value       = var.enable_openai ? "embedding" : null
}

output "azure_openai_chat_deployment" {
  description = "AZURE_OPENAI_CHAT_DEPLOYMENT に設定する値(enable_openai = false なら null)"
  value       = var.enable_openai ? "chat" : null
}

output "web_url" {
  description = "web の URL。/api/health が 200 なら DB に繋がっている"
  value       = module.containerapp.web_url
}

output "migrate_job_name" {
  description = "マイグレーション Job の名前(deploy.yml の変数 MIGRATE_JOB_NAME に設定する)"
  value       = module.containerapp.migrate_job_name
}

output "web_app_name" {
  description = "web の Container App 名(make deploy が使う)"
  value       = module.containerapp.web_name
}

output "recsys_app_name" {
  description = "recsys の Container App 名(make deploy が使う)"
  value       = module.containerapp.recsys_name
}

output "recsys_internal_url" {
  description = "RECSYS_URL に設定される値(環境の中からだけ届く)"
  value       = module.containerapp.recsys_internal_url
}

output "decider_url" {
  description = "STRANDS_DECIDER_URL に設定する値(外部 URL。decider_enabled のときだけ)"
  value       = var.decider_enabled ? module.decider[0].url : null
}

output "decider_app_name" {
  description = "判断モデルの Container App 名(decider_enabled のときだけ)"
  value       = var.decider_enabled ? module.decider[0].name : null
}

output "pipeline_job_name" {
  description = "pipeline の Container Apps Job 名(pipeline_job_enabled のときだけ)"
  value       = var.pipeline_job_enabled ? module.pipeline_job[0].name : null
}
