# ETL は Job にして決定モデルをパラメータで切り替える。データの更新は「動画だけ洗い替え」

- 日付: 2026-11-07
- 決定:
  - pipeline は、将来 Azure 上のジョブ(Container Apps Job)として動かせる形にする。決定モデルは `DECIDER_PROVIDER=rules|strands_azure` のパラメータで切り替える(失敗・低確信度のときに `rules` へ戻る動作は設計書 §8.3a のまま)。
  - 元 CSV は Blob の固定パス(`raw/<dataset_id>/*.csv`)に置き、その配下を全部読む。
  - 更新は「動画だけ洗い替え」。`videos` は `id` で upsert、`embeddings` と `clusters` は消して入れ直す。`impressions`・`view_events`・`like_events` は消さない(`publish.py` の現在の動作と同じ)。
  - ハッカソン(2026-11-08)のデモまでは、手元から `opendopa publish` を流す。ジョブ化と元 CSV の Blob 置き場は、デモの後に別 Issue で行う。
- 理由: ユーザー(proto08)の判断。ユーザーの履歴テーブルが `videos(id)` を外部キーで参照しているので、`videos` を消さずに入れ替える。
- 注意: 動画 ID は `<dataset_id>-<連番4桁>`(`build.py`)で、CSV の行順に依存する。同じ CSV なら同じ ID だが、行の増減・並べ替えがあると、履歴が別の動画を指す。元 CSV を差し替えるときは、行の順序を保つか、ID の付け方を見直す。
