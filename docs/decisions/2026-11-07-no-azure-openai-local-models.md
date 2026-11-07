# Azure OpenAI を使わず、埋め込みと判断モデルはローカルで動かす(取り消し済み)

> **取り消し(2026-11-07)**: 埋め込みは Azure OpenAI(`EMBED_PROVIDER=azure`)に戻し、判断モデルは Azure 上の自前モデル(`strands_azure`)にする(`2026-11-07-decider-on-azure-again.md`)。下の「決定」のうち、チャットモデルを使わない(`LLM_PROVIDER=none`)ことと、列定義 YAML の下書きを Claude Code が書くことは、そのまま有効。それ以外は履歴として残す。

- 日付: 2026-11-07
- 決定: 埋め込みは `EMBED_PROVIDER=local`(`multilingual-e5-large`)、判断モデルは評価に合格したら `jev_local`(それまでは `rules`)を既定にする。`LLM_PROVIDER` は `none`(クラスタ名は機械的な名前)。列定義 YAML の下書きは LLM API ではなく Claude Code が書く(`2026-11-07-draft-yaml-by-claude-code.md`)。モデルは、パイプラインを動かす PC で動かし、結果(ベクトル・シーン・音声)を `publish` で本番の DB と Blob に上げる。本番(Container Apps の web・recsys、DB、Blob/CDN)にモデルは載せない。設計書の §0.4、D14、§9 の Azure リソースと環境変数の表、M6b・§14.2b をこれに合わせた
- 理由: Azure OpenAI を使わない方針にしたため。判断モデルも、GPU 付き Container Apps(`strands_azure`)を立てるより、手元で動かす方が、用意と費用が小さい
- 注意: ローカルと Azure の埋め込みはモデルが違うので、ベクトルを混ぜない。本番の DB には、同じモデル・同じバージョンで作った分だけを入れる(publish する人を決める)
- 残っていること(別途): PR #113 とイシュー #58(`strands_azure` の配備)は不要になるので、クローズか縮小を人が決める。`infra/modules/openai` の削除、`.env.example` の `AZURE_OPENAI_*` の整理は、別PRで行う。TTS の Azure Speech は PR #116 で扱う
