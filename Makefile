# Terraform の入口(`mise run infra-*` も同じものを呼ぶ)。
# 事前に infra/backend.hcl(infra/bootstrap/bootstrap.sh が作る)と infra/terraform.tfvars を用意する。
TF_DIR := infra

.PHONY: infra-init infra-plan infra-apply infra-validate infra-fmt

infra-init:
	terraform -chdir=$(TF_DIR) init -backend-config=backend.hcl

infra-validate:
	terraform -chdir=$(TF_DIR) validate

infra-plan:
	terraform -chdir=$(TF_DIR) plan -out=tfplan

infra-apply:
	terraform -chdir=$(TF_DIR) apply tfplan

infra-fmt:
	terraform -chdir=$(TF_DIR) fmt -recursive
