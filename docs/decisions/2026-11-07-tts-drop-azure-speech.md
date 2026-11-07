# TTS は VOICEVOX だけにし、Azure AI Speech を使わない

- 日付: 2026-11-07
- Issue: #60
- 決定: `TTS_PROVIDER` は `none` と `voicevox` だけにする。Azure AI Speech の provider(`tts/providers.py` の `Azure`)、`AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION`、そのテストを削除し、設計書(§0.4、§9 の Azure リソース表、§9 の環境変数表、Terraform の対応表)も合わせる。`TTS_PROVIDER=azure` は「どれか」のエラーになる
- 理由: 採用は VOICEVOX と決めてあり、Azure は実機で一度も試していない(Speech リソースもない)。未検証のコードと、キー・リソースを用意する手間・費用を持ち込まないため。VOICEVOX は実エンジン(0.26.1)で合成と mp3 の長さの測定を確認した
- 補足: `infra/modules/speech`(Terraform)は、このPRでは消していない。不要になったので、別Issueで外す
