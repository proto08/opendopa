# lefthook の除外パスは、リポジトリのルートからの相対で書く

- 日付: 2026-11-07
- 決定: `lefthook.yml` の pipeline ジョブの `exclude` を、`root: pipeline/` からの相対(`opendopa_pipeline/generated/**`)ではなく、リポジトリのルートからの相対(`pipeline/opendopa_pipeline/generated/**`)で書く。
- 理由: lefthook の `exclude` は `root` を引いた後のパスではなく、リポジトリのルートからのパスと照合する。相対で書いていたので除外が効かず、pre-commit の ruff が生成ファイル(`pipeline/opendopa_pipeline/generated/scene.py`)の import を並べ替えていた。`mise run gen-types` の出力と食い違い、CI の「生成した型の差分」が落ちた(#160)。回避のための `--no-verify` も不要になる。
