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
