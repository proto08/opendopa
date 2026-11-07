# ADR-0143 デプロイ時にマイグレーションを流す

- Issue: #143
- 日付: 2026-11-07
- 状態: 決定

## A1 マイグレーションは Container Apps Job で流し、deploy.yml がアプリ更新の前に起動して待つ

- 決定: `db/Dockerfile`(dbmate 公式イメージ + `db/migrations`、CMD は `up`)をビルドして ACR に push し、Terraform で作った手動起動の Container Apps Job(`caj-<name>-migrate`)のイメージを差し替えて起動する。`deploy.yml` は実行状態が `Succeeded` になるまで待ち、`Failed` などか 10 分で終わらなければ失敗にして、アプリの更新に進まない。`MIGRATE_JOB_NAME` 変数が空のあいだはこの手順を飛ばす。
- 理由: Postgres は Azure 内サービスからのみ許可しており、CI のランナーから直接繋ぐには一時的なファイアウォール規則の作成・削除が要り、deploy 用のアプリ登録に Postgres 側の権限を足すことになる。Job なら Azure 内から繋がり、DATABASE_URL は Job のシークレット(Terraform が設定)に置くので、GitHub には長期のシークレットを増やさない(ADR-0019)。deploy 用の既存ロール(RG への Container Apps Contributor)で Job の更新・起動ができる。
- 注意: マイグレーションはアプリ更新の前に流れるので、旧アプリが動いているあいだに適用されても壊れない変更(expand/contract)にする。Job は管理者ロールの DATABASE_URL を持つ(web と同じ権限)。

## A2 Job 用の DATABASE_URL には `uselibpqcompat` を付けない

- 決定: web の URL(`uselibpqcompat=true` 付き)とは別に `migrate_database_url`(`sslmode=require` のみ)を Job に渡す。
- 理由: `uselibpqcompat` は node-postgres 向けの指定で、dbmate(Go の lib/pq)は未知のパラメータをサーバー設定として送り、失敗するため。
