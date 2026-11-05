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

module "storage" {
  source = "./modules/storage"

  # Storage Account の名前は英小文字・数字のみ・3〜24 文字・グローバルで一意
  name                 = "st${local.project}${var.env_name}${var.name_suffix}"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  cors_allowed_origins = var.cors_allowed_origins
  tags                 = local.tags
}

module "cdn" {
  source = "./modules/cdn"

  name                = local.name
  resource_group_name = azurerm_resource_group.main.name
  origin_host         = module.storage.primary_blob_host
  tags                = local.tags
}

module "openai" {
  source = "./modules/openai"

  name                = "oai-${local.name}${local.global_suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = local.params.openai_location
  deployments         = local.params.openai_deployments
  tags                = local.tags
}

# TTS_PROVIDER=azure のときだけ作る(既定の none / voicevox では作らない)
module "speech" {
  source = "./modules/speech"
  count  = var.tts_provider == "azure" ? 1 : 0

  name                = "spch-${local.name}${local.global_suffix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.tags
}
