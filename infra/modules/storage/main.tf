terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

variable "name" {
  description = "Storage Account 名(英小文字・数字のみ、3〜24 文字、グローバルで一意)"
  type        = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "replication_type" {
  type    = string
  default = "LRS"
}

variable "container_names" {
  description = "公開(匿名で読める)コンテナ"
  type        = list(string)
  default     = ["media", "scenes"]
}

variable "private_container_names" {
  description = "非公開コンテナ。raw は元 CSV の置き場(raw/<dataset_id>/*.csv。人が CSV を置く。Issue #144)"
  type        = list(string)
  default     = ["raw"]
}

variable "cors_allowed_origins" {
  description = "ブラウザが scenes の JSON を直接 fetch するときの許可オリジン"
  type        = list(string)
  default     = ["*"]
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_storage_account" "this" {
  name                     = var.name
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = var.replication_type
  min_tls_version          = "TLS1_2"

  # media / scenes は公開データ(音声とシーンJSON)。コンテナ単位で匿名の読み取りを許す
  allow_nested_items_to_be_public = true

  blob_properties {
    cors_rule {
      allowed_headers    = ["*"]
      allowed_methods    = ["GET", "HEAD"]
      allowed_origins    = var.cors_allowed_origins
      exposed_headers    = ["*"]
      max_age_in_seconds = 3600
    }
  }

  tags = var.tags
}

resource "azurerm_storage_container" "public" {
  for_each = toset(var.container_names)

  name                  = each.value
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "blob"
}

resource "azurerm_storage_container" "private" {
  for_each = toset(var.private_container_names)

  name                  = each.value
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

output "name" {
  value = azurerm_storage_account.this.name
}

output "id" {
  value = azurerm_storage_account.this.id
}

output "primary_blob_host" {
  description = "例: stopendopadev.blob.core.windows.net"
  value       = azurerm_storage_account.this.primary_blob_host
}

output "primary_connection_string" {
  value     = azurerm_storage_account.this.primary_connection_string
  sensitive = true
}
