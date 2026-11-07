# ADR-0017 Terraform でアプリ用リソース(DB・Storage・CDN・OpenAI)

- Issue: #17
- 日付: 2026-11-06
- 状態: 決定

## A1 PostgreSQL は VNet 統合なし・公開エンドポイント

- 決定: Flexible Server 16、SKU 既定 `B_Standard_B1ms`、`azure.extensions` に `VECTOR` を許可する。VNet 統合はせず、ファイアウォール規則 `0.0.0.0`(Azure 内サービスのみ許可)で Container Apps から繋ぐ。TLS(`sslmode=require`)とパスワード認証。`CREATE EXTENSION` は dbmate のマイグレーションで行う(設計書 §12.2)。
- 理由: ハッカソンの期間で VNet・プライベート DNS・Container Apps Environment の統合まで持ち込むと複雑になるため。手元から migrate するときは、必要に応じてクライアント IP の規則を人が足す。

## A2 秘密の値の渡し方: Key Vault は使わない

- 決定: 管理者パスワードは `sensitive` 変数 `postgres_admin_password`(環境変数 `TF_VAR_postgres_admin_password` で渡す。tfvars には書かない)。接続文字列・API キーは `sensitive = true` の output として出し、Container Apps のシークレットに後続イシューで渡す。Key Vault は作らない。
- 理由: 設計書 §12.1 で Key Vault は「任意」。参照する側(Container Apps のマネージド ID と権限付与)を足すと工数が増え、ハッカソンでは Container Apps のシークレットで足りる。state にキーが入るため、state の Storage へのアクセスは Azure AD で絞る(ADR-0016 A2)。

## A3 Front Door は 1 つのルートで media / scenes を Blob に流す

- 決定: Front Door Standard。オリジンは Blob の公開エンドポイント、`/media/*` と `/scenes/*` をパスを変えずに転送する。`MEDIA_BASE_URL` は `https://<endpoint>`。Blob のコンテナは `container_access_type = "blob"`(匿名読み取り)、CORS は既定 `*`(変数 `cors_allowed_origins` で絞れる)。
- 理由: 2 つのコンテナは同じオリジンで、パスの先頭がコンテナ名になるだけなので、ルート 1 つで足りる。

## A4 Azure OpenAI のモデルは `infra/main.parameters.json` で指定する(変数 `enable_openai` で作らない選択ができる。`docs/decisions/2026-11-07-minimal-infra-enable-switches.md`)

- 決定: 地域 `japaneast`、埋め込み `text-embedding-3-small`(version 1、Standard)、チャット `gpt-4o-mini`(2024-07-18、Standard)。デプロイ名は `embedding` / `chat`(`AZURE_OPENAI_*_DEPLOYMENT` の値)。
- 理由: 設計書 §12.1。**本物の apply・クォータの確認はしていない**(課金が発生するため)。apply で `Standard` が拒否された、またはモデルが Japan East にない場合は、`sku_name` を `GlobalStandard` に、`openai_location` を `eastus2` などに変えて、結果をここに追記する。

## A5 Speech は `tts_provider = "azure"` のときだけ作る

- 決定: 変数 `tts_provider`(既定 `none`)が `azure` のときだけ `modules/speech` を `count` で作る。output は `one()` で、作らないときは `null`。
- 理由: 設計書 §0.4(既定は none。採用は voicevox)。

## A6 リソース名の一意性

- 決定: PostgreSQL・Azure OpenAI・Speech は `<接頭辞>-opendopa-<env>[-<name_suffix>]`、Storage Account は `stopendopa<env><name_suffix>`。
- 理由: いずれもグローバルで一意が必要。衝突したら `name_suffix` を足す(ADR-0016 A4)。
