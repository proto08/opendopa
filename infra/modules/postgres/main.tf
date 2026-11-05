terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

variable "name" {
  description = "Server 名(グローバルで一意。例: opendopa-dev)"
  type        = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "administrator_login" {
  type = string
}

variable "administrator_password" {
  type      = string
  sensitive = true
}

variable "database_name" {
  type    = string
  default = "opendopa"
}

variable "sku_name" {
  type    = string
  default = "B_Standard_B1ms"
}

variable "storage_mb" {
  type    = number
  default = 32768
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_postgresql_flexible_server" "this" {
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location
  version             = "16"
  sku_name            = var.sku_name
  storage_mb          = var.storage_mb

  administrator_login    = var.administrator_login
  administrator_password = var.administrator_password

  # VNet 統合はしない(ハッカソンの簡素化)。公開エンドポイント + TLS + パスワード認証で、
  # 接続元はファイアウォール規則で絞る
  public_network_access_enabled = true
  backup_retention_days         = 7
  tags                          = var.tags

  lifecycle {
    ignore_changes = [zone]
  }
}

resource "azurerm_postgresql_flexible_server_database" "this" {
  name      = var.database_name
  server_id = azurerm_postgresql_flexible_server.this.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# `CREATE EXTENSION vector;` はアプリのマイグレーション(dbmate)で行う。ここでは許可リストに入れるだけ
resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.this.id
  value     = "VECTOR"
}

# 0.0.0.0 は「Azure 内のサービスからの接続を許可」の特別な指定(Container Apps から繋ぐため)
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure" {
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.this.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

output "server_name" {
  value = azurerm_postgresql_flexible_server.this.name
}

output "fqdn" {
  value = azurerm_postgresql_flexible_server.this.fqdn
}

output "database_name" {
  value = azurerm_postgresql_flexible_server_database.this.name
}

output "administrator_login" {
  value = var.administrator_login
}
