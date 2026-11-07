# Azure 環境のゼロからの再現手順は README に置き、実行は人が行う

- 日付: 2026-11-07
- Issue: #20
- 決定: 新しい `env_name` での構築・確認・`terraform destroy` の手順を README の「Azure 環境をゼロから作る・消す」に書く。手順の実行確認(実際の `make infra-apply` / `make deploy`)は、課金とアクセス権に関わるため自動化せず人が行う。
- 理由: 構築には Azure の課金とサブスクリプション権限が要り、無人の実装では実行できない。決定事項(地域 japaneast、モデル名、デプロイ方式)は ADR-0016〜0019 にあるため、`docs/DECISIONS.md` には足さない(2026-11-05 以降は1決定1ファイルの規約)。
- 関連: ADR-0017 A4、ADR-0018、ADR-0019
