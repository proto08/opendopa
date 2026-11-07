# Terraform の入口(`mise run infra-*` も同じものを呼ぶ)。
# 事前に infra/backend.hcl(infra/bootstrap/bootstrap.sh が作る)と infra/terraform.tfvars を用意する。
TF_DIR := infra
# 使うコマンド。OpenTofu なら `make TF=tofu infra-plan`(環境変数 TF=tofu でもよい)
TF ?= terraform

.PHONY: infra-init infra-plan infra-apply infra-validate infra-fmt deploy deploy-decider recsys-reload

infra-init:
	$(TF) -chdir=$(TF_DIR) init -backend-config=backend.hcl

infra-validate:
	$(TF) -chdir=$(TF_DIR) validate

infra-plan:
	$(TF) -chdir=$(TF_DIR) plan -out=tfplan

infra-apply:
	$(TF) -chdir=$(TF_DIR) apply tfplan

infra-fmt:
	$(TF) -chdir=$(TF_DIR) fmt -recursive

# イメージのビルド → Container Registry に push → Container Apps の更新(ADR-0018)。
# 事前に `az login` と、infra の apply(Registry と Container Apps が存在すること)が要る。
# 課金されるリソースを操作するため、人が実行する。
TAG ?= $(shell git rev-parse --short HEAD)
PLATFORM ?= linux/amd64

deploy:
	@set -eu; \
	login_server=$$($(TF) -chdir=$(TF_DIR) output -raw registry_login_server); \
	registry=$$($(TF) -chdir=$(TF_DIR) output -raw registry_name); \
	rg=$$($(TF) -chdir=$(TF_DIR) output -raw resource_group_name); \
	web_app=$$($(TF) -chdir=$(TF_DIR) output -raw web_app_name); \
	recsys_app=$$($(TF) -chdir=$(TF_DIR) output -raw recsys_app_name); \
	web_url=$$($(TF) -chdir=$(TF_DIR) output -raw web_url); \
	az acr login --name "$$registry"; \
	docker build --platform $(PLATFORM) -f services/recsys/Dockerfile -t "$$login_server/opendopa-recsys:$(TAG)" .; \
	docker build --platform $(PLATFORM) -f apps/web/Dockerfile -t "$$login_server/opendopa-web:$(TAG)" .; \
	docker push "$$login_server/opendopa-recsys:$(TAG)"; \
	docker push "$$login_server/opendopa-web:$(TAG)"; \
	az containerapp update -g "$$rg" -n "$$recsys_app" --image "$$login_server/opendopa-recsys:$(TAG)"; \
	az containerapp update -g "$$rg" -n "$$web_app" --image "$$login_server/opendopa-web:$(TAG)"; \
	echo "デプロイしました: $$web_url (確認: $$web_url/api/health)"

# recsys を再起動して、publish 後の新しい索引を起動時に読み直させる。
# recsys は内部 ingress のみで、手元 PC や CI から /internal/reload は届かないため。
# 事前に `az login` が要る。アクティブなリビジョンが複数ある場合は先頭の1つだけを再起動する。
recsys-reload:
	@set -eu; \
	rg=$$(terraform -chdir=$(TF_DIR) output -raw resource_group_name); \
	app=$$(terraform -chdir=$(TF_DIR) output -raw recsys_app_name); \
	rev=$$(az containerapp revision list -g "$$rg" -n "$$app" --query "[?properties.active].name | [0]" -o tsv); \
	test -n "$$rev" || { echo "アクティブなリビジョンが見つかりません" >&2; exit 1; }; \
	az containerapp revision restart -g "$$rg" -n "$$app" --revision "$$rev"; \
	echo "recsys を再起動しました: $$app ($$rev)"

# 判断モデル(strands_azure)の API サーバーのイメージを push して更新する。
# 事前に infra の decider_enabled = true で apply 済みであること。常時 1 レプリカが課金されるため、人が実行する。
# DECIDER_DOCKERFILE: 判断モデルのサーバーの Dockerfile(モデルの入手元・ライセンスの確認後に用意する)
DECIDER_DOCKERFILE ?= services/decider/Dockerfile

deploy-decider:
	@set -eu; \
	test -f "$(DECIDER_DOCKERFILE)" || { echo "$(DECIDER_DOCKERFILE) がありません"; exit 1; }; \
	login_server=$$($(TF) -chdir=$(TF_DIR) output -raw registry_login_server); \
	registry=$$($(TF) -chdir=$(TF_DIR) output -raw registry_name); \
	rg=$$($(TF) -chdir=$(TF_DIR) output -raw resource_group_name); \
	app=$$($(TF) -chdir=$(TF_DIR) output -raw decider_app_name); \
	az acr login --name "$$registry"; \
	docker build --platform $(PLATFORM) -f "$(DECIDER_DOCKERFILE)" -t "$$login_server/opendopa-decider:$(TAG)" .; \
	docker push "$$login_server/opendopa-decider:$(TAG)"; \
	az containerapp update -g "$$rg" -n "$$app" --image "$$login_server/opendopa-decider:$(TAG)"; \
	echo "判断モデルを更新しました。STRANDS_DECIDER_URL=$$($(TF) -chdir=$(TF_DIR) output -raw decider_url)"
