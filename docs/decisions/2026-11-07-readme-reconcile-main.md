# README を main の実装に合わせ、Azure 系の手順は「実機未確認」と明記する

- 日付: 2026-11-07
- Issue: #62
- 決定:
  - #144(pipeline ジョブ・`RAW_SOURCE=blob`・`fetch-raw`)、#146(BGM)、#154(BFF のタグ API)、`make deploy-pipeline` / `pipeline-run` / `deploy-decider`、`/sleep` の看板を README に足す。
  - タグ絞り込みは BFF の API までで、画面は未実装と書く。
  - Azure 向けの手順と、クリーンな環境での通し実行は確かめられていないため、「実機未確認」と書く。
- 理由: 受け入れ条件は「存在しないコマンドの記載がない」こと。実装と食い違う記述を避けるため、確かめた範囲と確かめていない範囲を分けて書く。
