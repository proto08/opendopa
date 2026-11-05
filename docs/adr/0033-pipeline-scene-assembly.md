# ADR-0033 パイプライン: 選定・テンプレート選択・シーン組み立て・コメント

- Issue: #33
- 日付: 2026-11-05
- 状態: 決定

## A1 `build_dataset` が 選定 → 判断 → 台本 → シーン → 検証 を通す

- 決定: `prepare()` の結果から、`select_rows`(select.py)→ `DecisionEngine`(#32。渡さなければ `rules`)→ `write_script`(script.py)→ `build_scene`(scene.py)・`generate_comments`(comments.py)→ `validate_scene` の順に、1行ずつ `Video` を作る(build.py)。`write_outputs` が `scenes.jsonl`(通った動画)と `videos.jsonl`(除外も含む)を `out/<id>/` に書く。`generate` コマンドへの接続と品質ゲート(§8.6)は #34。
- 理由: 受け入れ条件の「小さなフィクスチャの YAML から、スキーマを通るシーンが再現可能に作れる」を、コマンドに依存せず関数で確かめるため。

## A2 除外とエラーを分ける

- 決定: 台本が作れない行(`no_template` / `too_long`)、大きな数字が作れない行(`no_big_number`)、`pii` などの noul 判断で除外になった行(`decision:<id>`)は `status: excluded` と理由を記録する。組み立てたシーンがスキーマに合わないときは `SceneError` にする。
- 理由: 前者はデータ側の事情で、後者は生成側のバグ(イシューの指示)。除外の行も `videos.jsonl` に残すと、理由を後から集計できる。`pii` の除外は設計書 §8.6 の「判断」の検査だが、安全側の処理なので、判断の記録が手元にあるここで行う。

## A3 `csv_row` は全部出し、`hide` で除く

- 決定: `csv_row` は元の列を列の順に出す。個人に関わる列は YAML の `hide` に書いて除く。既定で出さない列はない。
- 理由: 画面の「元データ」の表示用なので、既定は全部出す。個人に関わる列の有無はデータセットごとの判断で、#34 の `accident.yaml` などで列を見て指定する(設計書 §15.2)。

## A4 コメントの決定的な乱数

- 決定: 種は `sha256("comments" + "\0" + videoId)` の先頭 8 バイト。Python の `hash()` は使わない。
- 理由: 同じ動画は毎回同じコメントにするため(§3.5)。テストで固定値を確かめ、種の作り方が変わると気づけるようにした。
