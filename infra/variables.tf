variable "env_name" {
  description = "環境名(例: dev)。リソース名に含める"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{2,8}$", var.env_name))
    error_message = "env_name は英小文字と数字の 2〜8 文字にする(Container Registry の名前制約のため)。"
  }
}

variable "location" {
  description = "リージョン(設計書 §12.1: Japan East)"
  type        = string
  default     = "japaneast"
}

variable "subscription_id" {
  description = "Azure のサブスクリプション ID。空なら az login の既定を使う"
  type        = string
  default     = ""
}

variable "name_suffix" {
  description = "Container Registry の名前はグローバルで一意にする必要があるため、衝突したときに足す英小文字・数字(例: チーム名)"
  type        = string
  default     = ""

  validation {
    condition     = can(regex("^[a-z0-9]{0,8}$", var.name_suffix))
    error_message = "name_suffix は英小文字と数字の 0〜8 文字にする。"
  }
}

variable "registry_sku" {
  description = "Container Registry の SKU"
  type        = string
  default     = "Basic"
}

variable "log_retention_days" {
  description = "Log Analytics のログ保持日数"
  type        = number
  default     = 30
}

variable "tags" {
  description = "全リソースに付ける追加のタグ"
  type        = map(string)
  default     = {}
}
