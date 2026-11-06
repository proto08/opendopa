# 判断モデル(Strands Decider 2B)の配備先: GPU 付き Container Apps(内部のみ)。
# 設計書 D14 / §12.1。GPU は workload profile の Container Apps Environment でだけ使えるため、
# 本体の Environment とは別に作る。VNet の内部ロードバランサーにして、外部には公開しない。
# 課金される(GPU)。infra/variables.tf の decider_enabled = true にしたときだけ作る。

terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

variable "name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  description = "GPU の割り当てがあるリージョン(Japan East で使えるかは配備前に要確認)"
  type        = string
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "registry_id" {
  type = string
}

variable "registry_login_server" {
  type = string
}

variable "image" {
  description = "判断モデルの API サーバーのイメージ。空なら公開のプレースホルダー(以後は az containerapp update が更新する)"
  type        = string
  default     = ""
}

variable "gpu_profile_type" {
  description = "GPU の workload profile(例: Consumption-GPU-NC8as-T4)"
  type        = string
  default     = "Consumption-GPU-NC8as-T4"
}

variable "token" {
  description = "内部 API の認証トークン(STRANDS_DECIDER_TOKEN と同じ値)"
  type        = string
  sensitive   = true

  # このモジュールは decider_enabled = true のときだけ作られるので、空のシークレットでの配備をここで止める
  validation {
    condition     = length(var.token) >= 16
    error_message = "decider を有効にするときは decider_token(16 文字以上)が必要。TF_VAR_decider_token で渡す。"
  }
}

variable "env" {
  description = "コンテナの環境変数(秘密でない値。モデル名など)"
  type        = map(string)
  default     = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  image = var.image != "" ? var.image : "mcr.microsoft.com/k8se/quickstart:latest"
}

resource "azurerm_virtual_network" "this" {
  name                = "vnet-${var.name}-decider"
  resource_group_name = var.resource_group_name
  location            = var.location
  address_space       = ["10.20.0.0/16"]
  tags                = var.tags
}

resource "azurerm_subnet" "this" {
  name                 = "snet-decider"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.20.0.0/23"]

  delegation {
    name = "containerapps"
    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_container_app_environment" "this" {
  name                           = "cae-${var.name}-decider"
  resource_group_name            = var.resource_group_name
  location                       = var.location
  log_analytics_workspace_id     = var.log_analytics_workspace_id
  infrastructure_subnet_id       = azurerm_subnet.this.id
  internal_load_balancer_enabled = true
  tags                           = var.tags

  workload_profile {
    name                  = "gpu"
    workload_profile_type = var.gpu_profile_type
  }
}

resource "azurerm_user_assigned_identity" "pull" {
  name                = "id-${var.name}-decider-acrpull"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = var.registry_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.pull.principal_id
}

resource "azurerm_container_app" "decider" {
  name                         = "ca-${var.name}-decider"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  workload_profile_name        = "gpu"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.pull.id]
  }

  registry {
    server   = var.registry_login_server
    identity = azurerm_user_assigned_identity.pull.id
  }

  secret {
    name  = "decider-token"
    value = var.token
  }

  ingress {
    external_enabled = false
    target_port      = 8000
    transport        = "http"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # モデルの読み込みが重いので、最小1(コールドスタートを避ける)
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "decider"
      image  = local.image
      cpu    = 8
      memory = "56Gi"

      env {
        name        = "STRANDS_DECIDER_TOKEN"
        secret_name = "decider-token"
      }
      dynamic "env" {
        for_each = var.env
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [azurerm_role_assignment.acr_pull]
}

output "name" {
  value = azurerm_container_app.decider.name
}

output "internal_url" {
  description = "STRANDS_DECIDER_URL に設定する値(VNet の中からだけ届く)"
  value       = "https://${azurerm_container_app.decider.ingress[0].fqdn}"
}
