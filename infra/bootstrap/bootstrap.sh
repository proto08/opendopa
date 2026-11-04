#!/usr/bin/env bash
# Terraform の state を置く Storage Account を作る(最初の1回だけ。冪等)。
# 前提: `az login` 済み。課金が発生するので、実行は人が行う。
#
# 使い方:
#   TFSTATE_SUFFIX=ab12 ENV_NAME=dev ./infra/bootstrap/bootstrap.sh
#
# 終わると infra/backend.hcl を書く。以降は `mise run infra-init`。
set -euo pipefail

: "${TFSTATE_SUFFIX:?Storage Account 名をグローバルで一意にする英小文字・数字(4〜8文字)を TFSTATE_SUFFIX に指定する}"
ENV_NAME="${ENV_NAME:-dev}"
LOCATION="${LOCATION:-japaneast}"
RG="rg-opendopa-tfstate"
SA="stopendopatfstate${TFSTATE_SUFFIX}"
CONTAINER="tfstate"

if ! [[ "$SA" =~ ^[a-z0-9]{3,24}$ ]]; then
  echo "Storage Account 名 '$SA' は英小文字・数字の 3〜24 文字にする必要がある" >&2
  exit 1
fi

az group create --name "$RG" --location "$LOCATION" --output none
az storage account create \
  --name "$SA" --resource-group "$RG" --location "$LOCATION" \
  --sku Standard_LRS --kind StorageV2 \
  --min-tls-version TLS1_2 --allow-blob-public-access false \
  --output none
az storage account blob-service-properties update \
  --account-name "$SA" --resource-group "$RG" --enable-versioning true --output none

# state の読み書きは Azure AD 認証で行う(アクセスキーを使わない)。自分に権限を付ける
SA_ID="$(az storage account show --name "$SA" --resource-group "$RG" --query id -o tsv)"
ME="$(az ad signed-in-user show --query id -o tsv)"
az role assignment create --assignee-object-id "$ME" --assignee-principal-type User \
  --role "Storage Blob Data Contributor" --scope "$SA_ID" --output none 2>/dev/null || true

az storage container create --name "$CONTAINER" --account-name "$SA" --auth-mode login --output none

OUT="$(cd "$(dirname "$0")/.." && pwd)/backend.hcl"
cat > "$OUT" <<HCL
resource_group_name  = "$RG"
storage_account_name = "$SA"
container_name       = "$CONTAINER"
key                  = "${ENV_NAME}.terraform.tfstate"
use_azuread_auth     = true
HCL
echo "書き込んだ: $OUT"
