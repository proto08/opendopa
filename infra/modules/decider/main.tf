# 判断モデル(Strands Decider 2B)の配備先: 本体と同じ Container Apps Environment の CPU の Container App。
# 設計書 D14 / §12.1(GPU 前提の記述は docs/decisions/2026-11-06-decider-cpu-external.md で読み替える)。
# 専用の VNet・Environment・内部ロードバランサー・GPU は使わない。ingress は外部で、Bearer トークンで守る。
# 課金される(常時 1 レプリカ)。infra/variables.tf の decider_enabled = true にしたときだけ作る。

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
  description = "本体と同じリージョン(japaneast)"
  type        = string
}

variable "environment_id" {
  description = "本体の Container Apps Environment の ID(modules/containerapp の output)"
  type        = string
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

variable "cpu" {
  description = "コンテナの CPU(consumption の上限は 4)"
  type        = number
  default     = 4
}

variable "memory" {
  description = "コンテナのメモリ(consumption の上限は 8Gi。cpu と組み合わせの制約がある)"
  type        = string
  default     = "8Gi"
}

variable "min_replicas" {
  description = "最小レプリカ数。モデルの読み込みが重いので 1(コールドスタートを避ける)。0 にすると止まっている間は課金されない"
  type        = number
  default     = 1
}

variable "token" {
  description = "API の認証トークン(STRANDS_DECIDER_TOKEN と同じ値)"
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
  container_app_environment_id = var.environment_id
  revision_mode                = "Single"
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
    external_enabled = true
    target_port      = 8000
    transport        = "http"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = 1

    container {
      name   = "decider"
      image  = local.image
      cpu    = var.cpu
      memory = var.memory

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

output "url" {
  description = "STRANDS_DECIDER_URL に設定する値(外部 URL。Bearer トークンが必要)"
  value       = "https://${azurerm_container_app.decider.ingress[0].fqdn}"
}
