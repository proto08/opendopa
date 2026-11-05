terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

variable "name" {
  description = "Azure OpenAI アカウント名(カスタムサブドメインにもなる。グローバルで一意)"
  type        = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  description = "Azure OpenAI を作るリージョン(モデルの提供状況で本体と異なってよい)"
  type        = string
}

variable "deployments" {
  description = "デプロイ名 => モデル。infra/main.parameters.json から渡す"
  type = map(object({
    model_name    = string
    model_version = string
    sku_name      = string
    capacity      = number
  }))
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_cognitive_account" "this" {
  name                  = var.name
  resource_group_name   = var.resource_group_name
  location              = var.location
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = var.name
  tags                  = var.tags
}

resource "azurerm_cognitive_deployment" "this" {
  for_each = var.deployments

  name                 = each.key
  cognitive_account_id = azurerm_cognitive_account.this.id

  model {
    format  = "OpenAI"
    name    = each.value.model_name
    version = each.value.model_version
  }

  sku {
    name     = each.value.sku_name
    capacity = each.value.capacity
  }
}

output "endpoint" {
  value = azurerm_cognitive_account.this.endpoint
}

output "primary_access_key" {
  value     = azurerm_cognitive_account.this.primary_access_key
  sensitive = true
}

output "deployment_names" {
  value = keys(azurerm_cognitive_deployment.this)
}
