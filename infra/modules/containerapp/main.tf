terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

variable "name" {
  description = "リソース名の共通部分(例: opendopa-dev)"
  type        = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "log_analytics_workspace_id" {
  description = "Container Apps Environment のログの送り先"
  type        = string
}

variable "registry_id" {
  description = "Container Registry のリソース ID(AcrPull を付与する)"
  type        = string
}

variable "registry_login_server" {
  type = string
}

variable "web_image" {
  description = "web のイメージ。空なら、レジストリに何も push していなくても作れるプレースホルダーを使う"
  type        = string
  default     = ""
}

variable "recsys_image" {
  description = "recsys のイメージ。空なら、プレースホルダーを使う"
  type        = string
  default     = ""
}

variable "web_env" {
  description = "web の環境変数(秘密でない値)"
  type        = map(string)
  default     = {}
}

variable "web_secrets" {
  description = "web のシークレット。キーが環境変数名になる(Container Apps のシークレット名は小文字とハイフンに変換する)"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "recsys_env" {
  description = "recsys の環境変数(秘密でない値)"
  type        = map(string)
  default     = {}
}

variable "recsys_secrets" {
  description = "recsys のシークレット。キーが環境変数名になる"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "migrate_image" {
  description = "マイグレーション Job のイメージ(db/Dockerfile)。空ならプレースホルダー(deploy.yml が差し替える)"
  type        = string
  default     = ""
}

variable "migrate_database_url" {
  description = "マイグレーション Job の DATABASE_URL(管理者ロール。dbmate は libpq 互換の uselibpqcompat を解さないため、付けない)"
  type        = string
  sensitive   = true
}

variable "web_min_replicas" {
  type    = number
  default = 1
}

variable "web_max_replicas" {
  type    = number
  default = 3
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  # イメージを push する前に apply できるよう、空のときは公開のプレースホルダーを使う。
  # 以後のイメージ更新は `az containerapp update`(make deploy)で行うため、下の lifecycle で差分を無視する。
  placeholder_image = "mcr.microsoft.com/k8se/quickstart:latest"
  web_image         = var.web_image != "" ? var.web_image : local.placeholder_image
  recsys_image      = var.recsys_image != "" ? var.recsys_image : local.placeholder_image
  migrate_image     = var.migrate_image != "" ? var.migrate_image : local.placeholder_image

  # for_each のキーは sensitive にできないため、キー(環境変数名)だけを取り出して使う
  web_secret_names    = nonsensitive(toset(keys(var.web_secrets)))
  recsys_secret_names = nonsensitive(toset(keys(var.recsys_secrets)))
}

resource "azurerm_container_app_environment" "this" {
  name                = "cae-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  # azurerm 5.x は logs_destination を明示しないと log_analytics_workspace_id を設定できない
  logs_destination           = "log-analytics"
  log_analytics_workspace_id = var.log_analytics_workspace_id
  tags                       = var.tags
}

# レジストリの管理者ユーザーは使わず、ユーザー割り当てマネージド ID + AcrPull でイメージを引く。
# (システム割り当てだと、アプリを作る前に AcrPull を付けられず、初回のイメージ取得に失敗するため)
resource "azurerm_user_assigned_identity" "pull" {
  name                = "id-${var.name}-acrpull"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = var.registry_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.pull.principal_id
}

# recsys: 内部のみ(external_enabled = false)。起動時に全動画をメモリへ読み込むため最小レプリカ1
resource "azurerm_container_app" "recsys" {
  name                         = "ca-${var.name}-recsys"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
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

  dynamic "secret" {
    for_each = local.recsys_secret_names
    content {
      name  = lower(replace(secret.value, "_", "-"))
      value = var.recsys_secrets[secret.value]
    }
  }

  ingress {
    external_enabled = false
    target_port      = 8080
    transport        = "http"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "recsys"
      image  = local.recsys_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "PORT"
        value = "8080"
      }
      dynamic "env" {
        for_each = var.recsys_env
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = local.recsys_secret_names
        content {
          name        = env.value
          secret_name = lower(replace(env.value, "_", "-"))
        }
      }
    }
  }

  lifecycle {
    # イメージは make deploy(az containerapp update)が更新する
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [azurerm_role_assignment.acr_pull]
}

# web: 外部公開。最小1・最大3
resource "azurerm_container_app" "web" {
  name                         = "ca-${var.name}-web"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
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

  dynamic "secret" {
    for_each = local.web_secret_names
    content {
      name  = lower(replace(secret.value, "_", "-"))
      value = var.web_secrets[secret.value]
    }
  }

  ingress {
    external_enabled = true
    target_port      = 3000
    transport        = "http"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.web_min_replicas
    max_replicas = var.web_max_replicas

    container {
      name   = "web"
      image  = local.web_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "RECSYS_URL"
        value = "https://${azurerm_container_app.recsys.ingress[0].fqdn}"
      }
      dynamic "env" {
        for_each = var.web_env
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = local.web_secret_names
        content {
          name        = env.value
          secret_name = lower(replace(env.value, "_", "-"))
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [azurerm_role_assignment.acr_pull]
}

# マイグレーション: 手動起動の Job。deploy.yml がイメージを差し替えて起動し、終わるまで待つ(ADR-0143)。
# Postgres は Azure 内サービスからの接続を許可しているため、CI のランナーの IP を許可する必要がない。
resource "azurerm_container_app_job" "migrate" {
  name                         = "caj-${var.name}-migrate"
  resource_group_name          = var.resource_group_name
  location                     = var.location
  container_app_environment_id = azurerm_container_app_environment.this.id
  tags                         = var.tags

  replica_timeout_in_seconds = 600
  # 再試行しない(失敗は人が原因を見る)
  replica_retry_limit = 0

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

  secret {
    name  = "database-url"
    value = var.migrate_database_url
  }

  template {
    container {
      name   = "migrate"
      image  = local.migrate_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [azurerm_role_assignment.acr_pull]
}

output "migrate_job_name" {
  value = azurerm_container_app_job.migrate.name
}

output "environment_id" {
  description = "Container Apps Environment の ID(decider など、同じ環境に Container App を足すときに使う)"
  value       = azurerm_container_app_environment.this.id
}

output "web_name" {
  value = azurerm_container_app.web.name
}

output "recsys_name" {
  value = azurerm_container_app.recsys.name
}

output "web_url" {
  description = "web の URL"
  value       = "https://${azurerm_container_app.web.ingress[0].fqdn}"
}

output "recsys_internal_url" {
  description = "recsys の内部 URL(Container Apps Environment の中からだけ届く)"
  value       = "https://${azurerm_container_app.recsys.ingress[0].fqdn}"
}
