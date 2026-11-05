provider "azurerm" {
  features {}

  # 空のときは az login の既定のサブスクリプションを使う
  subscription_id = var.subscription_id != "" ? var.subscription_id : null
}
