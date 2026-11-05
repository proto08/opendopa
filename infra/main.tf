locals {
  project = "opendopa"
  # リソース名の共通部分。例: opendopa-dev
  name = "${local.project}-${var.env_name}"

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
