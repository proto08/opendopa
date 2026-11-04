#!/usr/bin/env bash
# Claude Code の PostToolUse hook: 編集したファイルを、その言語の整形ツールで整える(ADR-0012 A16)。
# 整形に失敗しても編集は止めない(常に exit 0)。lint の違反は mise run lint と CI で拾う。
set -u

file=$(jq -r '.tool_input.file_path // empty')
[ -n "$file" ] && [ -f "$file" ] || exit 0

root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"
rel="${file#"$root"/}"

case "$rel" in
  packages/shared/src/generated/* | pipeline/opendopa_pipeline/generated/*)
    exit 0 ;; # 生成物は触らない
  apps/web/*.ts | apps/web/*.tsx | apps/web/*.mts | apps/web/*.js | apps/web/*.mjs)
    (cd "$root/apps/web" && mise exec -- pnpm exec eslint --fix "$file") >/dev/null 2>&1 ;;
  pipeline/*.py)
    (cd "$root/pipeline" && mise exec -- uv run ruff format "$file" && mise exec -- uv run ruff check --fix "$file") >/dev/null 2>&1 ;;
  services/recsys/*.rs)
    (cd "$root/services/recsys" && mise exec -- rustfmt --edition 2024 "$file") >/dev/null 2>&1 ;;
esac
exit 0
