locals {
  project = "opendopa"
  # リソース名の共通部分。例: opendopa-dev
  name = "${local.project}-${var.env_name}"

  # グローバルで一意にする必要があるリソース名の末尾(衝突したら name_suffix を足す)
  global_suffix = var.name_suffix != "" ? "-${var.name_suffix}" : ""

  # モデル名・地域などは設計書 §12.1 のとおり main.parameters.json で指定する
  params = jsondecode(file("${path.module}/main.parameters.json"))

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

# Azure OpenAI は任意(enable_openai)。最小構成(無料試用など)では false にできる
module "openai" {
  source = "./modules/openai"
  count  = var.enable_openai ? 1 : 0

  name                = "oai-${local.name}${local.global_suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = local.params.openai_location
  deployments         = local.params.openai_deployments
  tags                = local.tags
}

locals {
  # MEDIA_BASE_URL: cdn があれば Front Door、なければ Blob の公開 URL、storage もなければ空(音声・シーンの配信なし)
  media_base_url = (
    var.enable_cdn ? module.cdn[0].base_url :
    var.enable_storage ? "https://${module.storage[0].primary_blob_host}" : ""
  )

  # openai を作らないときは、AZURE_OPENAI_* を空にする(参照を壊さない)
  openai_env = {
    AZURE_OPENAI_ENDPOINT         = var.enable_openai ? module.openai[0].endpoint : ""
    AZURE_OPENAI_EMBED_DEPLOYMENT = var.enable_openai ? "embedding" : ""
  }
  # キーは秘密。空のシークレットは作れないので、openai があるときだけ渡す
  openai_secrets = var.enable_openai ? { AZURE_OPENAI_API_KEY = module.openai[0].primary_access_key } : {}

  # pg 8.x は sslmode=require を証明書検証ありとして扱う。uselibpqcompat=true で libpq 互換(暗号化のみ)にする
  database_url = format(
    "postgres://%s:%s@%s:5432/%s?sslmode=require&uselibpqcompat=true",
    module.postgres.administrator_login,
    urlencode(var.postgres_admin_password),
    module.postgres.fqdn,
    module.postgres.database_name,
  )
}

# dbmate(lib/pq)は uselibpqcompat を解さないため、マイグレーション Job にはそれを付けない URL を渡す
locals {
  migrate_database_url = format(
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
  migrate_database_url       = local.migrate_database_url
  web_min_replicas           = var.web_min_replicas
  web_max_replicas           = var.web_max_replicas

  web_env = merge(local.openai_env, {
    MEDIA_BASE_URL = local.media_base_url
    TTS_PROVIDER   = var.tts_provider
    TTS_CREDIT     = var.tts_credit
  })
  web_secrets = merge(local.openai_secrets, {
    DATABASE_URL                          = local.database_url
    INTERNAL_TOKEN                        = var.internal_token
    APPLICATIONINSIGHTS_CONNECTION_STRING = module.monitoring.application_insights_connection_string
  })

  recsys_env = merge(local.openai_env, {
    EMBED_DIM = "1024"
  })
  # RECSYS_DATABASE_URL は読み取り専用ロールの接続文字列。ロールを作るマイグレーションの後に tfvars で渡す
  recsys_secrets = merge(
    local.openai_secrets,
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

# pipeline のジョブ。手動で起動して、Blob の元 CSV から動画を洗い替える(pipeline_job_enabled。Issue #144)。
# 書き込みは publish.py と同じ(DB は管理者ロール。Blob は同じ Storage Account)。TTS はジョブからは届かない VOICEVOX
# を使うので none(音声つきの動画は、手元から `opendopa all` で公開する)。
module "pipeline_job" {
  source = "./modules/pipelinejob"
  count  = var.pipeline_job_enabled ? 1 : 0

  name                  = local.name
  resource_group_name   = azurerm_resource_group.main.name
  location              = azurerm_resource_group.main.location
  environment_id        = module.containerapp.environment_id
  registry_id           = module.registry.id
  registry_login_server = module.registry.login_server
  image                 = var.pipeline_image

  env = merge(local.openai_env, {
    RAW_SOURCE          = "blob"
    EMBED_PROVIDER      = "azure"
    EMBED_DIM           = "1024"
    TTS_PROVIDER        = "none"
    LLM_PROVIDER        = "none"
    DECIDER_PROVIDER    = var.pipeline_decider_provider
    MEDIA_BASE_URL      = local.media_base_url
    RECSYS_URL          = module.containerapp.recsys_internal_url
    STRANDS_DECIDER_URL = var.decider_enabled ? module.decider[0].url : ""
  })
  secrets = merge(
    local.openai_secrets,
    {
      DATABASE_URL              = local.database_url
      INTERNAL_TOKEN            = var.internal_token
      STORAGE_CONNECTION_STRING = module.storage[0].primary_connection_string
    },
    var.decider_enabled ? { STRANDS_DECIDER_TOKEN = var.decider_token } : {},
  )

  tags = local.tags
}
