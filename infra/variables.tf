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

  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.registry_sku)
    error_message = "registry_sku は Basic / Standard / Premium のいずれかにする。"
  }
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

variable "postgres_admin_login" {
  description = "PostgreSQL の管理者ログイン名"
  type        = string
  default     = "opendopa_admin"
}

variable "postgres_admin_password" {
  description = "PostgreSQL の管理者パスワード。tfvars に書かず、環境変数 TF_VAR_postgres_admin_password で渡す"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.postgres_admin_password) >= 16
    error_message = "postgres_admin_password は 16 文字以上にする。"
  }
}

variable "postgres_sku_name" {
  description = "PostgreSQL Flexible Server の SKU(既定は最小のバースト可能)"
  type        = string
  default     = "B_Standard_B1ms"
}

variable "cors_allowed_origins" {
  description = "Blob の CORS で許可するオリジン。web の URL が決まったら絞る"
  type        = list(string)
  default     = ["*"]
}

variable "tts_provider" {
  description = "web に渡す TTS_PROVIDER(none / voicevox)。voicevox のときだけフッターにクレジットを出す"
  type        = string
  default     = "none"

  validation {
    condition     = contains(["none", "voicevox"], var.tts_provider)
    error_message = "tts_provider は none / voicevox のどちらかにする。"
  }
}

variable "tts_credit" {
  description = "web のフッターに出すクレジット(TTS_CREDIT)。声を変えたら合わせる。空なら web の既定(VOICEVOX:ずんだもん)"
  type        = string
  default     = ""
}

variable "internal_token" {
  description = "web から recsys への内部 HTTP の共有トークン(INTERNAL_TOKEN)。環境変数 TF_VAR_internal_token で渡す"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.internal_token) >= 16
    error_message = "internal_token は 16 文字以上にする。"
  }
}

variable "recsys_database_url" {
  description = "RECSYS_DATABASE_URL(recsys が起動時に読む、読み取り専用ロールの接続文字列)。空なら recsys に渡さない。TF_VAR_recsys_database_url で渡す"
  type        = string
  default     = ""
  sensitive   = true
}

variable "web_image" {
  description = "web のイメージ(例: <registry>/opendopa-web:<tag>)。空なら初回用のプレースホルダー。以後の更新は make deploy が行い、Terraform は差分を無視する"
  type        = string
  default     = ""
}

variable "recsys_image" {
  description = "recsys のイメージ。web_image と同じ扱い"
  type        = string
  default     = ""
}

variable "web_min_replicas" {
  description = "web の最小レプリカ数"
  type        = number
  default     = 1
}

variable "web_max_replicas" {
  description = "web の最大レプリカ数"
  type        = number
  default     = 3
}
