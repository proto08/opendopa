# CLI は Typer のまま、サブコマンド方式で profile を実装した

- 日付: 2026-11-05
- Issue: #31
- 決定: CLI は Typer(#12 で導入済み)のまま、サブコマンド方式で `profile` を実装した。`profile` 以外の `generate`/`decide`/`embed`/`tts`/`publish`/`all` は「未実装」を出して終了コード 1 を返す。
