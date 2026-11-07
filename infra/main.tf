locals {
  project = "opendopa"
  # リソース名の共通部分。例: opendopa-dev
  name = "${local.project}-${var.env_name}"

  # グローバルで一意にする必要があるリソース名の末尾(衝突したら name_suffix を足す)
  global_suffix = var.name_suffix != "" ? "-${var.name_suffix}" : ""

  tags = merge(
    {
      project     = local.project
      environment = var.env_name
      managed_by  = "terraform"
    },
    var.tags,
  )
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}

module "monitoring" {
  source = "./modules/monitoring"

  name                = local.name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  retention_days      = var.log_retention_days
  tags                = local.tags
}

module "registry" {
  source = "./modules/registry"

  # ACR の名前は英数字のみ・5〜50 文字・グローバルで一意
  name                = "${local.project}${var.env_name}${var.name_suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = var.registry_sku
  tags                = local.tags
}

module "postgres" {
  source = "./modules/postgres"

  name                   = "psql-${local.name}${local.global_suffix}"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  administrator_login    = var.postgres_admin_login
  administrator_password = var.postgres_admin_password
  sku_name               = var.postgres_sku_name
  tags                   = local.tags
}

# Blob と配信は任意(enable_storage / enable_cdn)。最小構成では作らない選択ができる
module "storage" {
  source = "./modules/storage"
  count  = var.enable_storage ? 1 : 0

  # Storage Account の名前は英小文字・数字のみ・3〜24 文字・グローバルで一意
  name                 = "st${local.project}${var.env_name}${var.name_suffix}"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  cors_allowed_origins = var.cors_allowed_origins
  tags                 = local.tags
}

module "cdn" {
  source = "./modules/cdn"
  count  = var.enable_cdn ? 1 : 0

  name                = local.name
  resource_group_name = azurerm_resource_group.main.name
  origin_host         = module.storage[0].primary_blob_host
  tags                = local.tags
}

locals {
  # MEDIA_BASE_URL: cdn があれば Front Door、なければ Blob の公開 URL、storage もなければ空(音声・シーンの配信なし)
  media_base_url = (
    var.enable_cdn ? module.cdn[0].base_url :
    var.enable_storage ? "https://${module.storage[0].primary_blob_host}" : ""
  )

  database_url = format(
    "postgres://%s:%s@%s:5432/%s?sslmode=require",
    module.postgres.administrator_login,
    urlencode(var.postgres_admin_password),
    module.postgres.fqdn,
    module.postgres.database_name,
  )
}

# web と recsys。イメージは make deploy(az containerapp update)で差し替える(ADR-0018 A1)
module "containerapp" {
  source = "./modules/containerapp"

  name                       = local.name
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id
  registry_id                = module.registry.id
  registry_login_server      = module.registry.login_server
  web_image                  = var.web_image
  recsys_image               = var.recsys_image
  web_min_replicas           = var.web_min_replicas
  web_max_replicas           = var.web_max_replicas

  web_env = {
    MEDIA_BASE_URL = local.media_base_url
    TTS_PROVIDER   = var.tts_provider
    TTS_CREDIT     = var.tts_credit
  }
  web_secrets = {
    DATABASE_URL                          = local.database_url
    INTERNAL_TOKEN                        = var.internal_token
    APPLICATIONINSIGHTS_CONNECTION_STRING = module.monitoring.application_insights_connection_string
  }

  recsys_env = {
    EMBED_DIM = "1024"
  }
  # RECSYS_DATABASE_URL は読み取り専用ロールの接続文字列。ロールを作るマイグレーションの後に tfvars で渡す
  recsys_secrets = merge(
    { INTERNAL_TOKEN = var.internal_token },
    var.recsys_database_url != "" ? { RECSYS_DATABASE_URL = var.recsys_database_url } : {},
  )

  tags = local.tags
}

# 判断モデル(strands_azure)。常時 1 レプリカが課金されるので、既定では作らない(decider_enabled)
module "decider" {
  source = "./modules/decider"
  count  = var.decider_enabled ? 1 : 0

  name                  = local.name
  resource_group_name   = azurerm_resource_group.main.name
  location              = azurerm_resource_group.main.location
  environment_id        = module.containerapp.environment_id
  registry_id           = module.registry.id
  registry_login_server = module.registry.login_server
  image                 = var.decider_image
  cpu                   = var.decider_cpu
  memory                = var.decider_memory
  min_replicas          = var.decider_min_replicas
  token                 = var.decider_token

  tags = local.tags
}
