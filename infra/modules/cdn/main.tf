terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

variable "name" {
  description = "Front Door の名前の共通部分(例: opendopa-dev)"
  type        = string
}

variable "resource_group_name" {
  type = string
}

variable "origin_host" {
  description = "オリジン(Blob)のホスト名。例: stopendopadev.blob.core.windows.net"
  type        = string
}

variable "paths" {
  description = "配信するコンテナ名(パスの先頭になる)"
  type        = list(string)
  default     = ["media", "scenes"]
}

variable "sku_name" {
  type    = string
  default = "Standard_AzureFrontDoor"
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_cdn_frontdoor_profile" "this" {
  name                = "afd-${var.name}"
  resource_group_name = var.resource_group_name
  sku_name            = var.sku_name
  tags                = var.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "this" {
  name                     = "fde-${var.name}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  tags                     = var.tags
}

resource "azurerm_cdn_frontdoor_origin_group" "blob" {
  name                     = "blob"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id

  load_balancing {}
}

resource "azurerm_cdn_frontdoor_origin" "blob" {
  name                           = "blob"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.blob.id
  enabled                        = true
  host_name                      = var.origin_host
  origin_host_header             = var.origin_host
  certificate_name_check_enabled = true
  http_port                      = 80
  https_port                     = 443
}

# /media/* と /scenes/* をそのまま Blob の同名コンテナへ渡す(パスは変えない)
resource "azurerm_cdn_frontdoor_route" "blob" {
  name                          = "blob"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.this.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.blob.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.blob.id]

  patterns_to_match      = [for p in var.paths : "/${p}/*"]
  supported_protocols    = ["Http", "Https"]
  https_redirect_enabled = true
  forwarding_protocol    = "HttpsOnly"
  link_to_default_domain = true

  cache {
    query_string_caching_behavior = "IgnoreQueryString"
    compression_enabled           = true
    content_types_to_compress     = ["application/json", "text/plain"]
  }
}

output "endpoint_host" {
  value = azurerm_cdn_frontdoor_endpoint.this.host_name
}

output "base_url" {
  description = "MEDIA_BASE_URL に設定する値"
  value       = "https://${azurerm_cdn_frontdoor_endpoint.this.host_name}"
}
