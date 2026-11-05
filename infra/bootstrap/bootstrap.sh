#!/usr/bin/env bash
# Terraform の state を置く Storage Account を作る(最初の1回だけ。冪等)。
# 前提: `az login` 済み。課金が発生するので、実行は人が行う。
#
# 使い方:
#   TFSTATE_SUFFIX=ab12 ENV_NAME=dev ./infra/bootstrap/bootstrap.sh
#
# 終わると infra/backend.hcl を書く。以降は `mise run infra-init`。
set -euo pipefail

: "${TFSTATE_SUFFIX:?Storage Account 名をグローバルで一意にする英小文字・数字(4〜7文字)を TFSTATE_SUFFIX に指定する}"
ENV_NAME="${ENV_NAME:-dev}"
LOCATION="${LOCATION:-japaneast}"
RG="rg-opendopa-tfstate"
SA="stopendopatfstate${TFSTATE_SUFFIX}"
CONTAINER="tfstate"

# 接頭辞が 17 文字で、Storage Account 名は 24 文字までなので、接尾辞は 7 文字まで
if ! [[ "$TFSTATE_SUFFIX" =~ ^[a-z0-9]{4,7}$ ]]; then
  echo "TFSTATE_SUFFIX '$TFSTATE_SUFFIX' は英小文字・数字の 4〜7 文字にする必要がある" >&2
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
# 既に割り当て済みなら何もしない。権限不足などの失敗は、メッセージを出して止める
EXISTING="$(az role assignment list --assignee "$ME" --role "Storage Blob Data Contributor" \
  --scope "$SA_ID" --query "length(@)" -o tsv)"
if [ "$EXISTING" = "0" ]; then
  if ! az role assignment create --assignee-object-id "$ME" --assignee-principal-type User \
    --role "Storage Blob Data Contributor" --scope "$SA_ID" --output none; then
    echo "ロール割り当てに失敗した。Owner か User Access Administrator の権限が必要" >&2
    exit 1
  fi
fi

# ロール割り当ての反映には数分かかることがある。認可エラーの間はリトライする
for i in $(seq 1 12); do
  if az storage container create --name "$CONTAINER" --account-name "$SA" --auth-mode login --output none; then
    break
  fi
  if [ "$i" = "12" ]; then
    echo "コンテナの作成に失敗した。ロール割り当ての反映待ちか権限不足の可能性がある" >&2
    exit 1
  fi
  echo "ロール割り当ての反映待ち(${i}/12)。10 秒後に再試行する" >&2
  sleep 10
done

OUT="$(cd "$(dirname "$0")/.." && pwd)/backend.hcl"
cat > "$OUT" <<HCL
resource_group_name  = "$RG"
storage_account_name = "$SA"
container_name       = "$CONTAINER"
key                  = "${ENV_NAME}.terraform.tfstate"
use_azuread_auth     = true
HCL
echo "書き込んだ: $OUT"
