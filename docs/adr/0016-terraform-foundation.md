# ADR-0016 Terraform の土台と基盤リソース

- Issue: #16
- 日付: 2026-11-04
- 状態: 決定

## A1 azurerm のバージョンを 5.12.0 に固定する

- 決定: `versions.tf` で `hashicorp/azurerm` を `= 5.12.0`(レジストリの最新の安定版)に固定し、`.terraform.lock.hcl` をコミットする(darwin / linux の amd64・arm64 のハッシュを含む)。
- 理由: 設計書 §12.2 の方針。ハッカソン中に意図せず上がって plan が変わるのを防ぐ。

## A2 state のバックエンドは部分設定にする

- 決定: `backend "azurerm" {}` は空にし、接続先は `infra/backend.hcl`(コミットしない)で渡す。`backend.hcl.example` と、Storage Account を作る `infra/bootstrap/bootstrap.sh`(Azure CLI、冪等)を置く。認証は Azure AD(`use_azuread_auth`)で、アクセスキーは使わない。state の Blob にはバージョニングを有効にする。
- 理由: Storage Account 名はグローバルで一意にする必要があり、環境ごとに違うため、コードに書けない。bootstrap の実行は課金が発生するので人が行う。

## A3 入口は Makefile を本体とし、mise タスクから呼ぶ

- 決定: イシューの指定どおり `Makefile` に `infra-init` / `infra-plan` / `infra-apply`(と `infra-validate` / `infra-fmt`)を置く。設計書 §12.2 の `mise run infra-*` は、`make` を呼ぶ薄いタスクとして追加した。`infra-plan` は `tfplan` に保存し、`infra-apply` はその plan だけを apply する(確認した plan と違うものが適用されないようにする)。
- 理由: イシューと設計書の両方を満たす。`mise run lint` には `lint:infra`(fmt の検査と、バックエンドに接続しない validate)を足した。`terraform` は mise のツールに追加(1.16.2)。

## A4 リソース名と Container Registry の一意性

- 決定: 名前は `<種類の接頭辞>-opendopa-<env_name>`(例: `rg-opendopa-dev`、`log-`、`appi-`)。Container Registry は英数字のみで `opendopa<env_name><name_suffix>`。グローバルで一意にする必要があるため、衝突したら変数 `name_suffix` を足す。`env_name` は英小文字・数字の 2〜8 文字。
- 理由: ACR の名前制約(英数字、5〜50 文字、グローバル一意)。

## A5 Container Registry は Basic、管理者ユーザーなし

- 決定: SKU は既定 `Basic`(変数で変更可)、`admin_enabled = false`。Container Apps からはマネージド ID + AcrPull で引く(後続のイシューで設定)。
- 理由: 最小コストと、共有パスワードを持たないため。ローカルからの push は `az acr login` で行う。

## A6 Application Insights はワークスペースベース

- 決定: `workspace_id` に Log Analytics を指定する。保持日数は既定 30 日(変数 `log_retention_days`)。`connection_string` は `sensitive` の output にする。
- 理由: クラシック形式は廃止の方向のため。
