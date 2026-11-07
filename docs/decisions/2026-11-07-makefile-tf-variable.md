# Makefile の terraform コマンドを変数 `TF` にする(既定は terraform)

- 日付: 2026-11-07
- 決定: `Makefile` の `terraform` を `$(TF)` にし、既定は `TF ?= terraform` とする。OpenTofu を使う人は `make TF=tofu <ターゲット>` か環境変数 `TF=tofu` で切り替える。CI と既定の動きは変えない
- 理由: 手元に `tofu` だけを入れている人がいる。シェルの alias は `make` に効かないため
