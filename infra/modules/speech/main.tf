terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

variable "name" {
  description = "Speech アカウント名(グローバルで一意)"
  type        = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "sku_name" {
  type    = string
  default = "S0"
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_cognitive_account" "this" {
  name                  = var.name
  resource_group_name   = var.resource_group_name
  location              = var.location
  kind                  = "SpeechServices"
  sku_name              = var.sku_name
  custom_subdomain_name = var.name
  tags                  = var.tags
}

output "region" {
  description = "AZURE_SPEECH_REGION に設定する値"
  value       = azurerm_cognitive_account.this.location
}

output "primary_access_key" {
  value     = azurerm_cognitive_account.this.primary_access_key
  sensitive = true
}
