# pipeline の Container Apps Job(Issue #144)。手動で起動すると、Blob の元 CSV から動画を洗い替える:
# `opendopa all`(RAW_SOURCE=blob で Blob から取り込み → generate → tts → embed → publish → recsys の reload)。
# 本体と同じ Container Apps Environment で動かすので、recsys の内部 URL にそのまま届く。
# 起動したときだけ課金される(常時のレプリカはない)。infra/variables.tf の pipeline_job_enabled = true のときだけ作る。

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
  type = string
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
  description = "pipeline のイメージ。空なら公開のプレースホルダー(以後は make deploy-pipeline が更新する)"
  type        = string
  default     = ""
}

variable "cpu" {
  type    = number
  default = 2
}

variable "memory" {
  type    = string
  default = "4Gi"
}

variable "timeout_seconds" {
  description = "1 回の実行の上限(秒)"
  type        = number
  default     = 3600
}

variable "env" {
  description = "環境変数(秘密でない値)"
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "シークレット。キーが環境変数名になる(Container Apps のシークレット名は小文字とハイフンに変換する)"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  image        = var.image != "" ? var.image : "mcr.microsoft.com/k8se/quickstart:latest"
  secret_names = nonsensitive(toset(keys(var.secrets)))
}

resource "azurerm_user_assigned_identity" "pull" {
  name                = "id-${var.name}-pipeline-acrpull"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = var.registry_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.pull.principal_id
}

resource "azurerm_container_app_job" "pipeline" {
  name                         = "caj-${var.name}-pipeline"
  resource_group_name          = var.resource_group_name
  location                     = var.location
  container_app_environment_id = var.environment_id
  replica_timeout_in_seconds   = var.timeout_seconds
  replica_retry_limit          = 0
  tags                         = var.tags

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.pull.id]
  }

  registry {
    server   = var.registry_login_server
    identity = azurerm_user_assigned_identity.pull.id
  }

  dynamic "secret" {
    for_each = local.secret_names
    content {
      name  = lower(replace(secret.value, "_", "-"))
      value = var.secrets[secret.value]
    }
  }

  template {
    container {
      name   = "pipeline"
      image  = local.image
      cpu    = var.cpu
      memory = var.memory

      dynamic "env" {
        for_each = var.env
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = local.secret_names
        content {
          name        = env.value
          secret_name = lower(replace(env.value, "_", "-"))
        }
      }
    }
  }

  lifecycle {
    # イメージは make deploy-pipeline(az containerapp job update)が更新する
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [azurerm_role_assignment.acr_pull]
}

output "name" {
  value = azurerm_container_app_job.pipeline.name
}
