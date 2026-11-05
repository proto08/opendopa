terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

variable "name" {
  description = "Container Registry の名前(英数字のみ、グローバルで一意)"
  type        = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "sku" {
  type    = string
  default = "Basic"
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_container_registry" "this" {
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = var.sku
  # Container Apps からは後続のイシューでマネージド ID + AcrPull で引くため、管理者ユーザーは使わない
  admin_enabled = false
  tags          = var.tags
}

output "name" {
  value = azurerm_container_registry.this.name
}

output "id" {
  value = azurerm_container_registry.this.id
}

output "login_server" {
  value = azurerm_container_registry.this.login_server
}
