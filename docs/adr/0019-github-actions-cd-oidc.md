# ADR-0019 GitHub Actions の CD と Azure OIDC 認証

- Issue: #19
- 日付: 2026-11-06
- 状態: 決定

## A1 認証は OIDC のみ。アプリ登録は deploy 用と infra 用に分ける

- 決定: Azure へは `azure/login`(deploy)と azurerm の `ARM_USE_OIDC`(infra)で OIDC 認証する。アプリ登録は `opendopa-gh-deploy`(`AcrPush` + RG への `Container Apps Contributor`)と `opendopa-gh-infra`(サブスクリプションへの `Contributor` + `Role Based Access Control Administrator`、state の Storage への `Storage Blob Data Contributor`)の 2 つ。フェデレーション資格情報の subject は GitHub environment(`dev`、`infra-plan`、`infra-apply`)で絞る。
- 理由: 毎回のデプロイで使う権限(イメージの更新だけ)と、インフラを作り替える強い権限を分け、強い権限は承認付きの environment からしか使えないようにする。Terraform は ACR への `AcrPull` の割り当てを作るため、RBAC 管理の権限が要る。

## A2 デプロイ: main の CI 成功後に `workflow_run` で動かす

- 決定: `deploy.yml` は `workflow_run`(CI の完了、`main`、`push`、成功のみ)で動く。`workflow_dispatch` でも動く。イメージのタグは短縮 SHA。方式は ADR-0018 A1 のとおり `az containerapp update`(`make deploy` と同じ手順)で、最後に `/api/health` を確かめる。クライアント ID の変数が空のあいだは、何もせず成功で終わる。
- 理由: 「CI が通ったあとに動く」という要件を、CI の中に CD を足さずに満たすため。ci-ok の必須チェックを変えずに済む。設定前の main を赤くしないため、変数が空ならスキップする。

## A3 インフラ変更: plan と apply を別 environment に分け、plan ファイルを渡す

- 決定: `infra.yml`(`workflow_dispatch`)は `plan` ジョブ(`infra-plan`、承認なし)と `apply` ジョブ(`infra-apply`、Required reviewers)から成る。plan の結果を要約に出し、`tfplan` を artifact(保持 1 日)で apply に渡して、承認された plan をそのまま適用する。`backend.hcl` は変数(秘密でない)から作る。
- 理由: 承認した内容と適用される内容を一致させるため。plan ファイルには sensitive な値(DB パスワードなど)が入る。このリポジトリは public で、artifact は誰でもダウンロードできるため、`openssl enc -aes-256-cbc -pbkdf2` で暗号化してから上げ(パスフレーズは environment の secret `TF_PLAN_PASSPHRASE`。`infra-plan` と `infra-apply` の両方に同じ値を置く)、保持も 1 日にする。

## A4 Terraform の入力値(アプリの設定値)は environment secrets に置く

- 決定: `postgres_admin_password`、`internal_token`、`recsys_database_url` は `TF_VAR_*` として、`infra-plan` / `infra-apply` の environment secrets から渡す。Azure の資格情報(クライアントシークレットなど)は置かない。
- 理由: Terraform の必須変数で、state にも入る値。Azure の認証とは別物で、OIDC では代替できない。Key Vault 経由にする案は、ハッカソンの期間では構成が増えすぎるため見送る。

## A5 CI に Terraform の検査を足す

- 決定: `ci.yml` に `infra` ジョブ(`mise run lint:infra` = `terraform fmt -check` + `init -backend=false` + `validate`)を足し、`infra/**` の変更で走らせ、`ci-ok` の対象に含める。
- 理由: 既存の `lint:infra` タスクをそのまま使い、ローカルと CI の内容を揃える。
