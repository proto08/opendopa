terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "5.13.0"
    }
  }

  # state は Azure Storage の Blob に置く。接続先は環境ごとに違うため、
  # `backend.hcl`(bootstrap/bootstrap.sh が出力する形。コミットしない)で渡す。
  backend "azurerm" {}
}
